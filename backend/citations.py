import re
from difflib import SequenceMatcher

import httpx

from literature import UA, norm_title

STYLES = ["APA", "IEEE", "Vancouver", "Harvard", "BibTeX", "RIS"]
INTEXT_STYLES = ["APA", "IEEE", "Vancouver", "Harvard"]


def split_name(name: str) -> tuple[str, list[str]]:
    name = name.strip()
    if "," in name:
        family, given = [x.strip() for x in name.split(",", 1)]
    else:
        parts = name.split()
        family, given = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
    initials = [g[0].upper() for g in re.split(r"[\s.\-]+", given) if g]
    return family, initials


def _doi(p):
    return f"https://doi.org/{p['doi']}" if p.get("doi") else (p.get("url") or "")


def _authors(p, fmt, sep=", ", last=", & ", max_n=None):
    names = [fmt(*split_name(a)) for a in (p.get("authors") or []) if a.strip()]
    if not names:
        return "Unknown author"
    if max_n and len(names) > max_n:
        return sep.join(names[:max_n]) + sep + "et al."
    return names[0] if len(names) == 1 else sep.join(names[:-1]) + last + names[-1]


def fmt_apa(p):
    a = _authors(p, lambda f, i: f"{f}, {' '.join(x + '.' for x in i)}".strip(", "), max_n=20)
    return f"{a} ({p.get('year') or 'n.d.'}). {p['title']}.{' ' + p['journal'] + '.' if p.get('journal') else ''} {_doi(p)}".strip()


def fmt_harvard(p):
    a = _authors(p, lambda f, i: f"{f}, {''.join(x + '.' for x in i)}".strip(", "), last=" and ")
    s = f"{a} ({p.get('year') or 'n.d.'}) '{p['title']}'"
    s += f", {p['journal']}." if p.get("journal") else "."
    return s + (f" Available at: {_doi(p)}" if _doi(p) else "")


def fmt_ieee(p):
    a = _authors(p, lambda f, i: f"{' '.join(x + '.' for x in i)} {f}".strip(), last=" and " if len(p.get("authors") or []) == 2 else ", and ", max_n=6)
    s = f'{a}, "{p["title"]},"'
    if p.get("journal"):
        s += f" {p['journal']},"
    s += f" {p.get('year') or 'n.d.'}"
    return s + (f", doi: {p['doi']}." if p.get("doi") else (f". [Online]. Available: {p['url']}" if p.get("url") else "."))


def fmt_vancouver(p):
    a = _authors(p, lambda f, i: f"{f} {''.join(i)}".strip(), last=", ", max_n=6)
    s = f"{a.rstrip('.')}. {p['title']}."
    if p.get("journal"):
        s += f" {p['journal']}."
    s += f" {p.get('year') or 'n.d.'}."
    return s + (f" doi:{p['doi']}" if p.get("doi") else "")


def cite_key(p):
    fam = split_name((p.get("authors") or ["anon"])[0])[0] or "anon"
    word = next((w for w in re.findall(r"[A-Za-z]+", p["title"]) if len(w) > 3), "paper")
    return re.sub(r"[^a-z0-9]", "", f"{fam}{p.get('year') or ''}{word}".lower())


def fmt_bibtex(p):
    authors = " and ".join(f"{f}, {' '.join(x + '.' for x in i)}".strip(", ") for f, i in map(split_name, p.get("authors") or []))
    fields = [("author", authors), ("title", p["title"]), ("journal", p.get("journal")), ("year", p.get("year")),
              ("doi", p.get("doi")), ("url", p.get("url"))]
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@article{{{cite_key(p)},\n{body}\n}}"


def fmt_ris(p):
    lines = ["TY  - JOUR"]
    lines += [f"AU  - {f}, {' '.join(x + '.' for x in i)}".rstrip(", ") for f, i in map(split_name, p.get("authors") or [])]
    lines.append(f"TI  - {p['title']}")
    for tag, k in (("JO", "journal"), ("PY", "year"), ("DO", "doi"), ("UR", "url")):
        if p.get(k):
            lines.append(f"{tag}  - {p[k]}")
    lines.append("ER  - ")
    return "\n".join(lines)


FORMATTERS = {"APA": fmt_apa, "IEEE": fmt_ieee, "Vancouver": fmt_vancouver, "Harvard": fmt_harvard, "BibTeX": fmt_bibtex, "RIS": fmt_ris}


def format_all(p: dict) -> dict:
    return {s: f(p) for s, f in FORMATTERS.items()}


def in_text(papers: list[dict], style: str, numbers: list[int]) -> str:
    if style in ("IEEE", "Vancouver"):
        return "[" + ", ".join(str(n) for n in numbers) + "]"
    amp = " & " if style == "APA" else " and "
    parts = []
    for p in papers:
        fams = [split_name(a)[0] for a in (p.get("authors") or [])] or ["Unknown"]
        who = fams[0] if len(fams) == 1 else (amp.join(fams) if len(fams) == 2 else f"{fams[0]} et al.")
        parts.append(f"{who}, {p.get('year') or 'n.d.'}")
    return "(" + "; ".join(parts) + ")"


async def verify_doi(p: dict) -> dict:
    if not p.get("doi"):
        return {"status": "no_doi", "message": "This paper has no DOI, so it cannot be verified against Crossref.", "checks": []}
    try:
        async with httpx.AsyncClient(timeout=15, headers=UA) as c:
            r = await c.get(f"https://api.crossref.org/works/{p['doi']}")
        if r.status_code == 404:
            return {"status": "not_found", "message": "DOI not found in Crossref.", "checks": []}
        r.raise_for_status()
        m = r.json()["message"]
    except Exception as e:
        return {"status": "error", "message": f"Crossref unavailable: {str(e)[:120]}", "checks": []}
    cr_title = (m.get("title") or [""])[0]
    cr_year = ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    cr_journal = (m.get("container-title") or [""])[0]
    cr_first = ((m.get("author") or [{}])[0]).get("family") or ""
    my_first = split_name((p.get("authors") or [""])[0])[0] if p.get("authors") else ""
    sim = SequenceMatcher(None, norm_title(p.get("title")), norm_title(cr_title)).ratio()
    nj = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())  # noqa: E731
    checks = [
        {"field": "Title", "stored": p.get("title"), "crossref": cr_title, "match": sim >= 0.9},
        {"field": "Year", "stored": p.get("year"), "crossref": cr_year, "match": p.get("year") == cr_year},
        {"field": "Journal", "stored": p.get("journal"), "crossref": cr_journal,
         "match": bool(cr_journal) and bool(p.get("journal")) and (nj(cr_journal) in nj(p["journal"]) or nj(p["journal"]) in nj(cr_journal))},
        {"field": "First author", "stored": my_first, "crossref": cr_first,
         "match": bool(cr_first) and nj(cr_first) == nj(my_first)},
    ]
    for c in checks:
        if not c["stored"] and not c["crossref"]:
            c["match"] = None
    ok = all(c["match"] is not False for c in checks)
    return {"status": "verified" if ok else "mismatch",
            "message": "Metadata matches Crossref." if ok else "Some fields differ from Crossref — review before citing.", "checks": checks}
