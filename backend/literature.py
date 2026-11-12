import asyncio
import os
import re
import xml.etree.ElementTree as ET

import httpx

TIMEOUT = 15.0
PER_SOURCE = 20
UA = {"User-Agent": f"OptiNexusAI/1.0 (mailto:{os.environ.get('CONTACT_EMAIL', '')})"}
BOOL_RE = re.compile(r'"[^"]+"|\(|\)|\S+')


def tokenize(q: str) -> list[str]:
    return [t for t in BOOL_RE.findall(q) if t not in ("(", ")")]


def plain_terms(q: str) -> str:
    """Positive terms only (for APIs without Boolean support)."""
    toks, out, skip = tokenize(q), [], False
    for t in toks:
        if t in ("AND", "OR"):
            continue
        if t == "NOT":
            skip = True
            continue
        if not skip:
            out.append(t.strip('"'))
        skip = False
    return " ".join(out)


def arxiv_query(q: str, author: str) -> str:
    parts, toks = [], tokenize(q)
    op = None
    for t in toks:
        if t in ("AND", "OR", "NOT"):
            op = {"AND": "AND", "OR": "OR", "NOT": "ANDNOT"}[t]
            continue
        term = f'all:"{t.strip(chr(34))}"' if " " in t.strip('"') else f"all:{t}"
        if parts:
            parts.append(op or "AND")
        parts.append(term)
        op = None
    if author:
        parts += ["AND", f'au:"{author}"']
    return " ".join(parts)


def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def _rec(source, title, authors, year, journal, doi, url, abstract, oa, oa_url):
    return {"title": _clean(title), "authors": [a for a in authors if a], "year": year,
            "journal": _clean(journal) or None, "doi": (doi or "").lower().replace("https://doi.org/", "") or None,
            "url": url, "abstract": _clean(abstract) or None, "oa_available": oa, "oa_url": oa_url,
            "sources": [source]}


async def search_openalex(c, q, f):
    filters = []
    if f.get("year_from") or f.get("year_to"):
        filters.append(f"publication_year:{f.get('year_from') or ''}-{f.get('year_to') or ''}")
    params = {"search": q, "per-page": PER_SOURCE}
    if filters:
        params["filter"] = ",".join(filters)
    if os.environ.get("CONTACT_EMAIL"):
        params["mailto"] = os.environ["CONTACT_EMAIL"]
    r = await c.get("https://api.openalex.org/works", params=params)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        abstract = None
        if inv:
            pos = sorted((p, word) for word, ps in inv.items() for p in ps)
            abstract = " ".join(word for _, word in pos)
        loc = w.get("primary_location") or {}
        oa = w.get("open_access") or {}
        out.append(_rec("OpenAlex", w.get("title"), [a.get("author", {}).get("display_name") for a in w.get("authorships", [])],
                        w.get("publication_year"), (loc.get("source") or {}).get("display_name"), w.get("doi"),
                        w.get("doi") or loc.get("landing_page_url") or w.get("id"), abstract,
                        oa.get("is_oa"), oa.get("oa_url")))
    return out


async def search_crossref(c, q, f):
    params = {"query.bibliographic": plain_terms(q), "rows": PER_SOURCE,
              "select": "DOI,title,author,issued,container-title,abstract,URL"}
    flt = []
    if f.get("year_from"):
        flt.append(f"from-pub-date:{f['year_from']}")
    if f.get("year_to"):
        flt.append(f"until-pub-date:{f['year_to']}")
    if flt:
        params["filter"] = ",".join(flt)
    if f.get("author"):
        params["query.author"] = f["author"]
    if f.get("journal"):
        params["query.container-title"] = f["journal"]
    if os.environ.get("CONTACT_EMAIL"):
        params["mailto"] = os.environ["CONTACT_EMAIL"]
    r = await c.get("https://api.crossref.org/works", params=params)
    r.raise_for_status()
    out = []
    for it in r.json().get("message", {}).get("items", []):
        dp = (it.get("issued") or {}).get("date-parts") or [[None]]
        authors = [" ".join(x for x in [a.get("given"), a.get("family")] if x) or a.get("name") for a in it.get("author", [])]
        out.append(_rec("Crossref", (it.get("title") or [""])[0], authors, dp[0][0] if dp and dp[0] else None,
                        (it.get("container-title") or [None])[0], it.get("DOI"), it.get("URL"), it.get("abstract"),
                        None, None))
    return out


async def search_arxiv(c, q, f):
    r = await c.get("https://export.arxiv.org/api/query",
                    params={"search_query": arxiv_query(q, f.get("author")), "max_results": PER_SOURCE})
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), None)
        pub = e.findtext("a:published", "", ns)
        doi = e.findtext("arxiv:doi", None, ns)
        out.append(_rec("arXiv", e.findtext("a:title", "", ns), [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
                        int(pub[:4]) if pub[:4].isdigit() else None, e.findtext("arxiv:journal_ref", None, ns) or "arXiv preprint",
                        doi, e.findtext("a:id", "", ns), e.findtext("a:summary", "", ns), bool(pdf), pdf))
    return out


async def search_pubmed(c, q, f):
    term = q
    if f.get("author"):
        term += f' AND {f["author"]}[au]'
    if f.get("journal"):
        term += f' AND "{f["journal"]}"[ta]'
    if f.get("year_from") or f.get("year_to"):
        term += f' AND ({f.get("year_from") or 1800}:{f.get("year_to") or 3000}[dp])'
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    extra = {"api_key": os.environ["NCBI_API_KEY"]} if os.environ.get("NCBI_API_KEY") else {}
    r = await c.get(f"{base}/esearch.fcgi", params={"db": "pubmed", "term": term, "retmax": PER_SOURCE, "retmode": "json", **extra})
    r.raise_for_status()
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    r = await c.get(f"{base}/efetch.fcgi", params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml", **extra})
    r.raise_for_status()
    out = []
    for art in ET.fromstring(r.text).findall(".//PubmedArticle"):
        mc = art.find("MedlineCitation")
        a = mc.find("Article")
        year = a.findtext("Journal/JournalIssue/PubDate/Year") or (a.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
        authors = [" ".join(x for x in [au.findtext("ForeName"), au.findtext("LastName")] if x) or au.findtext("CollectiveName")
                   for au in a.findall("AuthorList/Author")]
        ids_ = {i.get("IdType"): i.text for i in art.findall("PubmedData/ArticleIdList/ArticleId")}
        pmc = ids_.get("pmc")
        abstract = " ".join("".join(t.itertext()) for t in a.findall("Abstract/AbstractText"))
        pmid = mc.findtext("PMID")
        out.append(_rec("PubMed", "".join(a.find("ArticleTitle").itertext()) if a.find("ArticleTitle") is not None else "",
                        authors, int(year) if year.isdigit() else None, a.findtext("Journal/Title"), ids_.get("doi"),
                        f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", abstract,
                        True if pmc else None, f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/" if pmc else None))
    return out


SEARCHERS = {"openalex": search_openalex, "crossref": search_crossref, "arxiv": search_arxiv, "pubmed": search_pubmed}


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def dedup_key(p: dict) -> str:
    return f"doi:{p['doi']}" if p.get("doi") else f"t:{norm_title(p['title'])}:{p.get('year')}"


def merge(results: list[dict]) -> list[dict]:
    merged, by_title = {}, {}
    for p in results:
        if not p.get("title"):
            continue
        tkey = f"t:{norm_title(p['title'])}:{p.get('year')}"
        key = dedup_key(p)
        existing = merged.get(key) or merged.get(by_title.get(tkey, ""))
        if existing:
            for s in p["sources"]:
                if s not in existing["sources"]:
                    existing["sources"].append(s)
            for k in ("doi", "abstract", "journal", "year", "url", "oa_url"):
                if not existing.get(k) and p.get(k):
                    existing[k] = p[k]
            if p.get("oa_available") and not existing.get("oa_available"):
                existing["oa_available"], existing["oa_url"] = True, p.get("oa_url") or existing.get("oa_url")
            if not existing["authors"]:
                existing["authors"] = p["authors"]
        else:
            merged[key] = p
            by_title[tkey] = key
    return list(merged.values())


def post_filter(papers, f):
    def ok(p):
        if f.get("year_from") and (not p.get("year") or p["year"] < int(f["year_from"])):
            return False
        if f.get("year_to") and (not p.get("year") or p["year"] > int(f["year_to"])):
            return False
        if f.get("author") and not any(f["author"].lower() in a.lower() for a in p["authors"]):
            return False
        if f.get("journal") and f["journal"].lower() not in (p.get("journal") or "").lower():
            return False
        return True
    return [p for p in papers if ok(p)]


async def search_all(query: str, filters: dict, enabled: list[str]) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        async def run(name):
            return await asyncio.wait_for(SEARCHERS[name](c, query, filters), TIMEOUT + 2)
        res = await asyncio.gather(*(run(n) for n in enabled), return_exceptions=True)
    status, combined = {}, []
    for name, r in zip(enabled, res):
        if isinstance(r, Exception):
            msg = "timed out" if isinstance(r, (asyncio.TimeoutError, httpx.TimeoutException)) else f"{type(r).__name__}: {str(r)[:160]}"
            status[name] = {"ok": False, "error": msg, "count": 0}
        else:
            status[name] = {"ok": True, "count": len(r)}
            combined.extend(r)
    papers = post_filter(merge(combined), filters)
    return {"results": papers, "sources": status, "raw_count": len(combined)}
