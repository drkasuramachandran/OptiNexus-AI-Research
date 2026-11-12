import io
import re

from docx import Document
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import llm
from agents import system_prompt, paper_summary, scoped_papers, retrieve, STANDING_RULES
from citations import format_all, in_text, verify_doi, FORMATTERS, INTEXT_STYLES
from core import db, CurrentUser, get_settings, assert_project, new_id, now_iso, log_activity
from documents import wrap_data
from llm import parse_json

router = APIRouter(prefix="/api")
NOT_REPORTED = "Not reported"


async def _llm_json(uid: str, system: str, prompt: str) -> dict:
    s = await get_settings(uid)
    try:
        return parse_json(await llm.complete(s["model"], system, prompt))
    except llm.LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI request failed: {str(e)[:200]}")


def basis(p):
    return "full text" if p.get("origin") == "upload" else ("abstract + metadata" if p.get("abstract") else "metadata only")


def clean_val(v, papers: list[dict]) -> str:
    s = str(v or NOT_REPORTED).strip()
    if s.lower().startswith("not reported"):
        return NOT_REPORTED
    sub = lambda m: f"“{papers[int(m.group(1)) - 1]['title'][:50]}”" if 1 <= int(m.group(1)) <= len(papers) else ""  # noqa: E731
    return re.sub(r"\[?\bP(\d+)\b\]?", sub, s)


async def material(uid: str, p: dict, query: str, k: int = 3) -> str:
    text = paper_summary(p)
    if p.get("origin") == "upload":
        hits = await retrieve(uid, [p["id"]], query, k)
        text += "\n" + "\n".join(f"[{p.get('filename')}, p.{h['page']}, {h['section']}] {h['text']}" for h in hits)
    return text


async def project_papers(uid: str, project_id: str, paper_ids: list[str]) -> list[dict]:
    await assert_project(uid, project_id)
    papers = await db.papers.find({"user_id": uid, "project_ids": project_id, "id": {"$in": paper_ids}}, {"_id": 0}).to_list(50)
    order = {pid: i for i, pid in enumerate(paper_ids)}
    return sorted(papers, key=lambda p: order[p["id"]])


# ---------- Citations ----------
@router.get("/papers/{paper_id}/citations")
async def citations(paper_id: str, user=CurrentUser):
    p = await db.papers.find_one({"id": paper_id, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Paper not found")
    return {"formats": format_all(p), "verification": p.get("verification")}


@router.post("/papers/{paper_id}/verify")
async def verify(paper_id: str, user=CurrentUser):
    p = await db.papers.find_one({"id": paper_id, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Paper not found")
    v = {**(await verify_doi(p)), "checked_at": now_iso()}
    await db.papers.update_one({"id": paper_id, "user_id": user["id"]}, {"$set": {"verification": v}})
    return v


# ---------- Structured gap discovery ----------
GAP_TAGS = ["Directly reported limitation", "Pattern inferred across studies", "AI suggestion"]
GAP_SCHEMA = """Return ONLY JSON: {"gaps": [{"research_area": "...", "supporting_papers": ["P1", "P3"], "limitations_found": "...",
"unresolved_questions": "...", "proposed_direction": "...", "evidence_strength": "Low|Medium|High", "strength_reason": "...",
"tag": "Directly reported limitation|Pattern inferred across studies|AI suggestion"}]}
Give 3-6 gaps. supporting_papers must use only the [P#] labels provided. 'Directly reported limitation' requires a limitation stated in a paper;
'Pattern inferred across studies' requires at least two papers; anything else is 'AI suggestion'. Evidence strength must reflect how many papers
support the gap and whether full text or only abstracts were available."""


@router.post("/conversations/{cid}/gaps")
async def structured_gaps(cid: str, user=CurrentUser):
    uid = user["id"]
    conv = await db.conversations.find_one({"id": cid, "user_id": uid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    papers = await scoped_papers(uid, conv.get("project_id"))
    if not papers:
        raise HTTPException(400, "No papers in this scope. Save or upload papers first.")
    q = "limitation limitations future work unresolved challenge not evaluated drawback"
    body = "\n\n".join([f"[P{i+1}]\n{await material(uid, p, q)}" for i, p in enumerate(papers)])
    n, full = len(papers), sum(1 for p in papers if p.get("origin") == "upload")
    data = await _llm_json(uid, system_prompt("gap_discovery") + "\n\n" + GAP_SCHEMA,
                           f"Number of papers: {n}.\n\n" + wrap_data("PAPERS", body) + "\n\nReturn the JSON now.")
    items = []
    for g in data.get("gaps", [])[:6]:
        sup = []
        for lab in g.get("supporting_papers", []):
            m = re.match(r"P(\d+)", str(lab))
            if m and 1 <= int(m.group(1)) <= n:
                p = papers[int(m.group(1)) - 1]
                if p["id"] not in [s["id"] for s in sup]:
                    sup.append({"id": p["id"], "title": p["title"], "year": p.get("year"), "basis": basis(p)})
        tag = g.get("tag") if g.get("tag") in GAP_TAGS else "AI suggestion"
        if (tag == GAP_TAGS[0] and not sup) or (tag == GAP_TAGS[1] and len(sup) < 2):
            tag = "AI suggestion"
        strength = g.get("evidence_strength") if g.get("evidence_strength") in ("Low", "Medium", "High") else "Low"
        if not sup:
            strength = "Low"
        items.append({k: clean_val(g.get(k), papers) for k in ("research_area", "limitations_found", "unresolved_questions", "proposed_direction", "strength_reason")}
                     | {"supporting_papers": sup, "tag": tag, "evidence_strength": strength})
    gaps = {"papers_analysed": n, "full_text_count": full, "items": items}
    summary = f"Structured gap analysis based on {n} papers ({full} full text, {n - full} abstract/metadata only). " \
              f"{len(items)} candidate gaps. Novelty is not guaranteed — verify with further literature and patent searches."
    summary += "".join(f"\n\n{i+1}. **{g['research_area']}** — {g['tag']}, evidence {g['evidence_strength']}. "
                       f"Supporting: {', '.join(s['title'] for s in g['supporting_papers']) or 'none'}. Direction: {g['proposed_direction']}"
                       for i, g in enumerate(items))
    now = now_iso()
    msgs = [{"id": new_id(), "role": "user", "content": "Run a structured research gap analysis.", "created_at": now},
            {"id": new_id(), "role": "assistant", "content": summary, "mode": "gap_discovery", "mode_label": "Research Gap Discovery (structured)",
             "papers_in_context": n, "gaps": gaps, "created_at": now}]
    upd = {"$push": {"messages": {"$each": msgs}}, "$set": {"updated_at": now}}
    if not conv["messages"]:
        upd["$set"]["title"] = "Structured gap analysis"
    await db.conversations.update_one({"id": cid, "user_id": uid}, upd)
    await log_activity(uid, f"Ran structured gap analysis on {n} papers", "gap")
    return {"messages": msgs}


# ---------- Paper comparison ----------
COMPARE_FIELDS = ["objectives", "methodology", "instruments", "parameters", "conditions", "results", "limitations"]


class CompareIn(BaseModel):
    project_id: str
    paper_ids: list[str] = Field(min_length=2, max_length=6)


@router.post("/compare")
async def compare(body: CompareIn, user=CurrentUser):
    uid = user["id"]
    papers = await project_papers(uid, body.project_id, list(dict.fromkeys(body.paper_ids)))
    if not 2 <= len(papers) <= 6:
        raise HTTPException(400, "Select 2 to 6 papers from this project.")
    q = "objective method setup instrument parameter condition temperature wavelength result sensitivity limitation"
    data_body = "\n\n".join([f"[P{i+1}]\n{await material(uid, p, q, 4)}" for i, p in enumerate(papers)])
    system = system_prompt("paper_comparison") + f"""\n\nReturn ONLY JSON: {{"rows": [{{"paper": "P1", {", ".join(f'"{f}": "..."' for f in COMPARE_FIELDS)}}}]}}
One row per paper label. Each value concise (max ~40 words), taken only from that paper's DATA. Use exactly "{NOT_REPORTED}" when absent."""
    data = await _llm_json(uid, system, wrap_data("PAPERS", data_body) + "\n\nReturn the JSON now.")
    by_label = {str(r.get("paper")): r for r in data.get("rows", [])}
    rows = []
    for i, p in enumerate(papers):
        r = by_label.get(f"P{i+1}", {})
        rows.append({"paper_id": p["id"], "title": p["title"], "year": p.get("year"), "basis": basis(p),
                     **{f: clean_val(r.get(f), papers) for f in COMPARE_FIELDS}})
    await log_activity(uid, f"Compared {len(rows)} papers", "compare")
    return {"fields": COMPARE_FIELDS, "rows": rows}


# ---------- Writing studio ----------
DOC_TYPES = {"proposal": "research proposal", "literature_review": "literature review", "abstract": "abstract (max 300 words)",
             "manuscript_section": "manuscript section"}
CITE_RE = re.compile(r"\[(R\d+(?:\s*[,;]\s*R?\d+)*)\]")


class DraftIn(BaseModel):
    project_id: str
    paper_ids: list[str] = Field(min_length=1, max_length=20)
    doc_type: str
    style: str
    instructions: str = ""


def apply_citations(text: str, papers: list[dict], style: str) -> tuple[str, list[int]]:
    order: list[int] = []

    def repl(m):
        idx = [int(x) for x in re.findall(r"\d+", m.group(1))]
        valid = [i for i in idx if 1 <= i <= len(papers)]
        if not valid:
            return "[UNSUPPORTED: citation not in project]"
        for i in valid:
            if i not in order:
                order.append(i)
        return in_text([papers[i - 1] for i in valid], style, [order.index(i) + 1 for i in valid])

    return CITE_RE.sub(repl, text), order


@router.post("/writing/draft")
async def draft(body: DraftIn, user=CurrentUser):
    uid = user["id"]
    if body.doc_type not in DOC_TYPES or body.style not in INTEXT_STYLES:
        raise HTTPException(400, "Unknown document type or citation style")
    papers = await project_papers(uid, body.project_id, list(dict.fromkeys(body.paper_ids)))
    if not papers:
        raise HTTPException(400, "Select source papers from this project.")
    project = await assert_project(uid, body.project_id)
    q = f"{body.instructions} {project.get('objectives', '')} results methods conclusions"
    src = "\n\n".join([f"[R{i+1}]\n{await material(uid, p, q, 4)}" for i, p in enumerate(papers)])
    system = f"""You are a scientific writing assistant drafting a {DOC_TYPES[body.doc_type]} in Markdown.
Citation rules:
- Cite sources ONLY with markers like [R1] or [R1, R3], using only the [R#] labels provided. Never invent other references or DOIs.
- Every claim taken from a source must carry its marker.
- Any sentence making a factual/scientific claim NOT supported by the provided sources must end with the inline flag [UNSUPPORTED].
- Do not add a reference list; it is generated automatically.
- Never mention the R# labels outside square-bracket citation markers, and do not write notes about inputs or source availability; write only the document itself.

{STANDING_RULES}"""
    prompt = (f"Project: {project['title']}\nObjectives: {project.get('objectives') or '-'}\nResearch questions: {project.get('research_questions') or '-'}\n"
              f"User instructions: {body.instructions or '-'}\n\n" + wrap_data("SOURCE PAPERS", src) + "\n\nWrite the draft now.")
    s = await get_settings(uid)
    try:
        raw = await llm.complete(s["model"], system, prompt)
    except llm.LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI request failed: {str(e)[:200]}")
    text, order = apply_citations(raw.strip(), papers, body.style)
    cited = [papers[i - 1] for i in order]
    if body.style in ("APA", "Harvard"):
        cited_sorted = sorted(cited, key=lambda p: ((p.get("authors") or ["~"])[0].split()[-1].lower(), p.get("year") or 0))
        refs = [FORMATTERS[body.style](p) for p in cited_sorted]
        ref_md = "\n\n".join(refs)
    else:
        ref_md = "\n\n".join(f"[{n}] {FORMATTERS[body.style](p)}" for n, p in enumerate(cited, 1))
    if cited:
        text += "\n\n## References\n\n" + ref_md
    await log_activity(uid, f"Generated {DOC_TYPES[body.doc_type]} draft", "writing")
    return {"markdown": text, "unsupported_count": len(re.findall(r"\[UNSUPPORTED", text)),
            "cited": [p["title"] for p in cited], "uncited": [p["title"] for p in papers if p not in cited]}


class DraftSaveIn(BaseModel):
    project_id: str
    title: str = Field(min_length=1)
    markdown: str
    doc_type: str = ""
    style: str = ""
    paper_ids: list[str] = []


@router.get("/drafts")
async def list_drafts(project_id: str, user=CurrentUser):
    await assert_project(user["id"], project_id)
    return await db.drafts.find({"user_id": user["id"], "project_id": project_id}, {"_id": 0}).sort("updated_at", -1).to_list(500)


@router.post("/drafts")
async def create_draft(body: DraftSaveIn, user=CurrentUser):
    await assert_project(user["id"], body.project_id)
    d = {"id": new_id(), "user_id": user["id"], **body.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.drafts.insert_one(dict(d))
    d.pop("_id", None)
    return d


@router.put("/drafts/{did}")
async def update_draft(did: str, body: DraftSaveIn, user=CurrentUser):
    await assert_project(user["id"], body.project_id)
    r = await db.drafts.update_one({"id": did, "user_id": user["id"]}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Draft not found")
    return await db.drafts.find_one({"id": did}, {"_id": 0})


@router.delete("/drafts/{did}")
async def delete_draft(did: str, user=CurrentUser):
    await db.drafts.delete_one({"id": did, "user_id": user["id"]})
    return {"ok": True}


class DocxIn(BaseModel):
    title: str = "Draft"
    markdown: str


def _runs(par, text):
    for i, part in enumerate(re.split(r"\*\*", text)):
        if part:
            par.add_run(part.replace("*", "")).bold = i % 2 == 1


@router.post("/writing/docx")
async def to_docx(body: DocxIn, user=CurrentUser):
    doc = Document()
    for line in body.markdown.splitlines():
        s = line.rstrip()
        if not s.strip():
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            doc.add_heading(m.group(2).replace("*", ""), level=min(len(m.group(1)), 4))
        elif re.match(r"^\s*[-*]\s+", s):
            _runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*]\s+", "", s))
        elif re.match(r"^\s*\d+\.\s+", s):
            _runs(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+\.\s+", "", s))
        else:
            _runs(doc.add_paragraph(), s)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", body.title)[:60] or "draft"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})
