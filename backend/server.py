from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

import llm
from agents import MODES, route_mode, system_prompt, build_context, retrieve, STANDING_RULES
from core import (db, client, now_iso, new_id, hash_password, verify_password, create_token, CurrentUser,
                  get_settings, assert_project, log_activity, SOURCES)
from documents import extract_pages, chunk_pages, wrap_data, PDFError, MAX_BYTES
from literature import search_all, norm_title

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="OptiNexus AI API")


@app.get("/health")
async def health():
    """Lightweight Render health check; does not expose secrets or database details."""
    return {"status": "ok", "service": "optinexus-api"}


api = APIRouter(prefix="/api")
NOT_FOUND = "Not found in document"
PROFILE_FIELDS = ["title", "authors", "year", "journal", "doi", "problem", "objectives", "methods", "experimental_setup",
                  "instruments", "parameters", "results", "limitations", "conclusions", "future_work"]


# ---------- Auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@api.post("/auth/register")
async def register(body: RegisterIn):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user = {"id": new_id(), "email": email, "name": body.name.strip(), "created_at": now_iso()}
    await db.users.insert_one({**user, "password_hash": hash_password(body.password)})
    await get_settings(user["id"])
    return {"token": create_token(user["id"], email), "user": user}


@api.post("/auth/login")
async def login(body: LoginIn):
    email = body.email.lower()
    att = await db.login_attempts.find_one({"identifier": email})
    if att and att.get("until", "") <= now_iso():
        att = None
    if att and att.get("count", 0) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    u = await db.users.find_one({"email": email})
    if not u or not verify_password(body.password, u["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": email}, {"$set": {"count": count, "until": until}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": email})
    user = {k: u[k] for k in ("id", "email", "name", "created_at")}
    return {"token": create_token(u["id"], email), "user": user}


@api.get("/auth/me")
async def me(user=CurrentUser):
    return user


class ProfileIn(BaseModel):
    name: str = Field(min_length=1)


@api.put("/auth/profile")
async def update_profile(body: ProfileIn, user=CurrentUser):
    await db.users.update_one({"id": user["id"]}, {"$set": {"name": body.name.strip()}})
    return {**user, "name": body.name.strip()}


# ---------- Settings ----------
class SettingsIn(BaseModel):
    model: Optional[str] = None
    sources: Optional[dict] = None


def key_status():
    def st(k):
        return "configured" if os.environ.get(k) else "missing"
    return [
        {"key": "GEMINI_API_KEY", "purpose": "Google Gemini model access (required for AI features)", "status": st("GEMINI_API_KEY"), "required": True},
        {"key": "CONTACT_EMAIL", "purpose": "Polite-pool contact for OpenAlex / Crossref (optional)", "status": st("CONTACT_EMAIL"), "required": False},
        {"key": "NCBI_API_KEY", "purpose": "Higher PubMed rate limit (optional)", "status": st("NCBI_API_KEY"), "required": False},
    ]


@api.get("/settings")
async def read_settings(user=CurrentUser):
    s = await get_settings(user["id"])
    return {"model": s["model"], "sources": s["sources"], "models": llm.MODELS, "keys": key_status(), "modes": {k: v["label"] for k, v in MODES.items()}}


@api.put("/settings")
async def write_settings(body: SettingsIn, user=CurrentUser):
    upd = {}
    if body.model:
        if body.model not in llm.MODEL_IDS:
            raise HTTPException(400, "Unknown model")
        upd["model"] = body.model
    if body.sources is not None:
        upd["sources"] = {k: bool(body.sources.get(k, True)) for k in SOURCES}
    await get_settings(user["id"])
    await db.settings.update_one({"user_id": user["id"]}, {"$set": upd})
    return await read_settings(user)


# ---------- Projects ----------
class ProjectIn(BaseModel):
    title: str = Field(min_length=1)
    objectives: str = ""
    research_questions: str = ""


@api.get("/projects")
async def list_projects(user=CurrentUser):
    items = await db.projects.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    for p in items:
        p["paper_count"] = await db.papers.count_documents({"user_id": user["id"], "project_ids": p["id"]})
    return items


@api.post("/projects")
async def create_project(body: ProjectIn, user=CurrentUser):
    p = {"id": new_id(), "user_id": user["id"], **body.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.projects.insert_one(dict(p))
    await log_activity(user["id"], f"Created project “{body.title}”", "project")
    p.pop("_id", None)
    return p


@api.get("/projects/{pid}")
async def get_project(pid: str, user=CurrentUser):
    return await assert_project(user["id"], pid)


@api.put("/projects/{pid}")
async def update_project(pid: str, body: ProjectIn, user=CurrentUser):
    await assert_project(user["id"], pid)
    await db.projects.update_one({"id": pid, "user_id": user["id"]}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    return await assert_project(user["id"], pid)


@api.delete("/projects/{pid}")
async def delete_project(pid: str, user=CurrentUser):
    p = await assert_project(user["id"], pid)
    uid = user["id"]
    await db.projects.delete_one({"id": pid, "user_id": uid})
    await db.papers.update_many({"user_id": uid, "project_ids": pid}, {"$pull": {"project_ids": pid}})
    for coll in (db.notes, db.conversations, db.reports, db.drafts):
        await coll.delete_many({"user_id": uid, "project_id": pid})
    await log_activity(uid, f"Deleted project “{p['title']}”", "project")
    return {"ok": True}


# ---------- Literature search ----------
class SearchIn(BaseModel):
    query: str = Field(min_length=2)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    author: Optional[str] = None
    journal: Optional[str] = None


@api.post("/search")
async def search(body: SearchIn, user=CurrentUser):
    s = await get_settings(user["id"])
    enabled = [k for k in SOURCES if s["sources"].get(k, True)]
    if not enabled:
        raise HTTPException(400, "All literature sources are disabled in Settings.")
    res = await search_all(body.query, body.model_dump(exclude={"query"}), enabled)
    res["disabled"] = [k for k in SOURCES if k not in enabled]
    await log_activity(user["id"], f"Searched “{body.query}” ({len(res['results'])} results)", "search")
    return res


# ---------- Papers / Library ----------
class PaperIn(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    oa_available: Optional[bool] = None
    oa_url: Optional[str] = None
    sources: list[str] = []
    project_id: Optional[str] = None


class PaperPatch(BaseModel):
    tags: Optional[list[str]] = None
    project_ids: Optional[list[str]] = None


@api.post("/papers")
async def save_paper(body: PaperIn, user=CurrentUser):
    uid = user["id"]
    if body.project_id:
        await assert_project(uid, body.project_id)
    q = {"user_id": uid, "doi": body.doi} if body.doi else {"user_id": uid, "title_key": norm_title(body.title), "year": body.year}
    existing = await db.papers.find_one(q, {"_id": 0})
    if existing:
        if body.project_id and body.project_id not in existing.get("project_ids", []):
            await db.papers.update_one({"id": existing["id"]}, {"$addToSet": {"project_ids": body.project_id}})
            existing["project_ids"].append(body.project_id)
        return {**existing, "already_saved": True}
    data = body.model_dump(exclude={"project_id"})
    p = {"id": new_id(), "user_id": uid, **data, "title_key": norm_title(body.title), "origin": "search", "status": "ready",
         "tags": [], "project_ids": [body.project_id] if body.project_id else [], "created_at": now_iso()}
    await db.papers.insert_one(dict(p))
    await log_activity(uid, f"Saved paper “{body.title[:80]}”", "paper")
    p.pop("_id", None)
    return p


@api.get("/papers")
async def list_papers(q: str = "", tag: str = "", project_id: str = "", origin: str = "", user=CurrentUser):
    flt = {"user_id": user["id"]}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        flt["$or"] = [{"title": rx}, {"authors": rx}, {"journal": rx}, {"doi": rx}, {"tags": rx}, {"filename": rx}]
    if tag:
        flt["tags"] = tag
    if project_id:
        await assert_project(user["id"], project_id)
        flt["project_ids"] = project_id
    if origin:
        flt["origin"] = origin
    return await db.papers.find(flt, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.get("/papers/{paper_id}")
async def get_paper(paper_id: str, user=CurrentUser):
    p = await db.papers.find_one({"id": paper_id, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Paper not found")
    return p


@api.patch("/papers/{paper_id}")
async def patch_paper(paper_id: str, body: PaperPatch, user=CurrentUser):
    await get_paper(paper_id, user)
    upd = {}
    if body.tags is not None:
        upd["tags"] = sorted({t.strip() for t in body.tags if t.strip()})
    if body.project_ids is not None:
        for pid in body.project_ids:
            await assert_project(user["id"], pid)
        upd["project_ids"] = list(dict.fromkeys(body.project_ids))
    await db.papers.update_one({"id": paper_id, "user_id": user["id"]}, {"$set": upd})
    return await get_paper(paper_id, user)


@api.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str, user=CurrentUser):
    await get_paper(paper_id, user)
    await db.papers.delete_one({"id": paper_id, "user_id": user["id"]})
    await db.chunks.delete_many({"paper_id": paper_id, "user_id": user["id"]})
    return {"ok": True}


# ---------- PDF upload & analysis ----------
from llm import parse_json


PROFILE_SYSTEM = f"""You extract a structured profile from ONE scientific document.
Return ONLY a JSON object with exactly these keys: {", ".join(PROFILE_FIELDS)}.
Each value must be a string taken from the document text (authors as a comma-separated string, year as a 4-digit string).
If the document does not explicitly contain the information for a field, the value MUST be exactly "{NOT_FOUND}". Never guess, infer or use outside knowledge.
Keep each value concise (max ~80 words) and reference page numbers like (p.3) where helpful.

{STANDING_RULES}"""


async def analyze_paper(user_id: str, paper_id: str, pages: list[str], filename: str):
    try:
        settings = await get_settings(user_id)
        body = "\n".join(f"[Page {i+1}]\n{t}" for i, t in enumerate(pages))[:90000]
        raw = await llm.complete(settings["model"], PROFILE_SYSTEM, wrap_data(f"DOCUMENT {filename}", body) + "\n\nReturn the JSON profile now.")
        data = parse_json(raw)
        full = " ".join(pages).lower()
        profile = {}
        for f in PROFILE_FIELDS:
            v = data.get(f)
            v = str(v).strip() if v not in (None, "", []) else NOT_FOUND
            profile[f] = v
        doi = profile["doi"].lower().replace("https://doi.org/", "").strip()
        if profile["doi"] != NOT_FOUND and doi not in full:
            profile["doi"] = NOT_FOUND
        upd = {"profile": profile, "status": "ready"}
        if profile["title"] != NOT_FOUND:
            upd["title"] = profile["title"]
        if profile["authors"] != NOT_FOUND:
            upd["authors"] = [a.strip() for a in profile["authors"].split(",") if a.strip()]
        if profile["year"][:4].isdigit():
            upd["year"] = int(profile["year"][:4])
        if profile["journal"] != NOT_FOUND:
            upd["journal"] = profile["journal"]
        if profile["doi"] != NOT_FOUND:
            upd["doi"] = doi
        await db.papers.update_one({"id": paper_id, "user_id": user_id}, {"$set": upd})
        await log_activity(user_id, f"Analyzed PDF “{filename}”", "upload")
    except Exception as e:
        logger.exception("analysis failed")
        msg = str(e) if isinstance(e, llm.LLMUnavailable) else f"AI profile generation failed: {str(e)[:200]}"
        await db.papers.update_one({"id": paper_id, "user_id": user_id}, {"$set": {"status": "profile_failed", "error": msg}})


@api.post("/papers/upload")
async def upload_pdfs(background: BackgroundTasks, files: list[UploadFile] = File(...), project_id: str = Form(""), user=CurrentUser):
    uid = user["id"]
    if project_id:
        await assert_project(uid, project_id)
    results = []
    for f in files:
        name = f.filename or "document.pdf"
        data = await f.read(MAX_BYTES + 1)
        err = None
        if not name.lower().endswith(".pdf") or (f.content_type and f.content_type not in ("application/pdf", "application/x-pdf", "application/octet-stream")):
            err = "Only PDF files are accepted."
        elif len(data) > MAX_BYTES:
            err = "File exceeds the 20 MB limit."
        if not err:
            try:
                pages = extract_pages(data)
            except PDFError as e:
                err = str(e)
        if err:
            results.append({"filename": name, "ok": False, "error": err})
            continue
        digest = hashlib.sha256(data).hexdigest()
        dup = await db.papers.find_one({"user_id": uid, "sha256": digest}, {"_id": 0, "id": 1})
        if dup:
            if project_id:
                await db.papers.update_one({"id": dup["id"]}, {"$addToSet": {"project_ids": project_id}})
            results.append({"filename": name, "ok": False, "error": "Already uploaded — existing copy reused" + (" and linked to the project." if project_id else "."), "paper_id": dup["id"]})
            continue
        chunks = chunk_pages(pages)
        pid = new_id()
        paper = {"id": pid, "user_id": uid, "title": name.rsplit(".", 1)[0], "title_key": norm_title(name), "authors": [],
                 "year": None, "journal": None, "doi": None, "url": None, "abstract": None, "oa_available": None,
                 "sources": ["Upload"], "origin": "upload", "filename": name, "page_count": len(pages),
                 "chunk_count": len(chunks), "status": "processing", "tags": [], "sha256": digest,
                 "project_ids": [project_id] if project_id else [], "created_at": now_iso()}
        await db.papers.insert_one(dict(paper))
        if chunks:
            await db.chunks.insert_many([{"id": new_id(), "user_id": uid, "paper_id": pid, **c} for c in chunks])
        background.add_task(analyze_paper, uid, pid, pages, name)
        results.append({"filename": name, "ok": True, "paper_id": pid, "pages": len(pages), "chunks": len(chunks)})
    return {"results": results}


@api.post("/papers/{paper_id}/reanalyze")
async def reanalyze(paper_id: str, background: BackgroundTasks, user=CurrentUser):
    p = await get_paper(paper_id, user)
    if p.get("origin") != "upload":
        raise HTTPException(400, "Only uploaded PDFs can be analyzed")
    chunks = await db.chunks.find({"user_id": user["id"], "paper_id": paper_id}, {"_id": 0}).sort("chunk_index", 1).to_list(20000)
    pages = [""] * p["page_count"]
    for c in chunks:
        pages[c["page"] - 1] += " " + c["text"]
    await db.papers.update_one({"id": paper_id}, {"$set": {"status": "processing", "error": None}})
    background.add_task(analyze_paper, user["id"], paper_id, pages, p["filename"])
    return {"ok": True}


class QAIn(BaseModel):
    question: str = Field(min_length=3)
    paper_id: Optional[str] = None
    project_id: Optional[str] = None


QA_SYSTEM = f"""You answer questions strictly from the numbered document excerpts provided (S1, S2, ...).
Return ONLY JSON: {{"evidence_found": true|false, "answer": "...", "citations": [{{"source": "S1", "excerpt": "short verbatim quote copied exactly from that excerpt"}}]}}
- Every factual sentence in the answer must cite a source marker like [S1].
- Excerpts must be copied verbatim (max 40 words) from the cited source.
- If the excerpts do not contain evidence to answer, set evidence_found=false, answer="No supporting evidence found in the selected documents." and citations=[].

{STANDING_RULES}"""


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


@api.post("/qa")
async def qa(body: QAIn, user=CurrentUser):
    uid = user["id"]
    flt = {"user_id": uid, "origin": "upload"}
    if body.paper_id:
        flt["id"] = body.paper_id
    elif body.project_id:
        await assert_project(uid, body.project_id)
        flt["project_ids"] = body.project_id
    else:
        raise HTTPException(400, "Choose a paper or a project")
    papers = await db.papers.find(flt, {"_id": 0, "id": 1, "filename": 1}).to_list(500)
    if not papers:
        raise HTTPException(400, "No uploaded PDFs in this scope")
    names = {p["id"]: p["filename"] for p in papers}
    hits = await retrieve(uid, list(names), body.question)
    no_ev = {"evidence_found": False, "answer": "No supporting evidence found in the selected documents.", "citations": [], "documents_searched": len(papers)}
    if not hits:
        return no_ev
    srcs = "\n\n".join(f"[S{i+1}] document: {names[h['paper_id']]} | page {h['page']} | section: {h['section']}\n{h['text']}" for i, h in enumerate(hits))
    s = await get_settings(uid)
    try:
        data = parse_json(await llm.complete(s["model"], QA_SYSTEM, wrap_data("DOCUMENT EXCERPTS", srcs) + f"\n\nQuestion: {body.question}"))
    except llm.LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI answer failed: {str(e)[:200]}")
    if not data.get("evidence_found"):
        return no_ev
    cites = []
    for c in data.get("citations", []):
        m = re.match(r"S(\d+)", str(c.get("source", "")))
        if not m or not (1 <= int(m.group(1)) <= len(hits)):
            continue
        h = hits[int(m.group(1)) - 1]
        ex = c.get("excerpt", "")
        verified = bool(ex) and _norm(ex) in _norm(h["text"])
        cites.append({"source": f"S{m.group(1)}", "document": names[h["paper_id"]], "paper_id": h["paper_id"], "page": h["page"],
                      "section": h["section"], "excerpt": ex if verified else h["text"][:260] + "…", "verbatim": verified})
    if not cites:
        return no_ev
    await log_activity(uid, f"Asked: “{body.question[:80]}”", "qa")
    return {"evidence_found": True, "answer": data.get("answer", ""), "citations": cites, "documents_searched": len(papers)}


# ---------- Notes ----------
class NoteIn(BaseModel):
    title: str = Field(min_length=1)
    content: str = ""
    project_id: Optional[str] = None


@api.get("/notes")
async def list_notes(project_id: str = "", user=CurrentUser):
    flt = {"user_id": user["id"]}
    if project_id:
        flt["project_id"] = project_id
    return await db.notes.find(flt, {"_id": 0}).sort("updated_at", -1).to_list(1000)


@api.post("/notes")
async def create_note(body: NoteIn, user=CurrentUser):
    if body.project_id:
        await assert_project(user["id"], body.project_id)
    n = {"id": new_id(), "user_id": user["id"], **body.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.notes.insert_one(dict(n))
    n.pop("_id", None)
    return n


@api.put("/notes/{nid}")
async def update_note(nid: str, body: NoteIn, user=CurrentUser):
    if body.project_id:
        await assert_project(user["id"], body.project_id)
    r = await db.notes.update_one({"id": nid, "user_id": user["id"]}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Note not found")
    return await db.notes.find_one({"id": nid}, {"_id": 0})


@api.delete("/notes/{nid}")
async def delete_note(nid: str, user=CurrentUser):
    await db.notes.delete_one({"id": nid, "user_id": user["id"]})
    return {"ok": True}


# ---------- Reports ----------
class ReportIn(BaseModel):
    title: str = Field(min_length=1)
    content: str
    project_id: str


@api.get("/reports")
async def list_reports(project_id: str, user=CurrentUser):
    await assert_project(user["id"], project_id)
    return await db.reports.find({"user_id": user["id"], "project_id": project_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/reports")
async def create_report(body: ReportIn, user=CurrentUser):
    await assert_project(user["id"], body.project_id)
    r = {"id": new_id(), "user_id": user["id"], **body.model_dump(), "created_at": now_iso()}
    await db.reports.insert_one(dict(r))
    r.pop("_id", None)
    return r


@api.delete("/reports/{rid}")
async def delete_report(rid: str, user=CurrentUser):
    await db.reports.delete_one({"id": rid, "user_id": user["id"]})
    return {"ok": True}


# ---------- Conversations / Assistant ----------
class ConvIn(BaseModel):
    title: str = "New conversation"
    project_id: Optional[str] = None


class MsgIn(BaseModel):
    content: str = Field(min_length=1)
    mode: str = "auto"


@api.get("/conversations")
async def list_convs(project_id: str = "", user=CurrentUser):
    flt = {"user_id": user["id"]}
    if project_id:
        flt["project_id"] = project_id
    return await db.conversations.find(flt, {"_id": 0, "messages": 0}).sort("updated_at", -1).to_list(500)


@api.post("/conversations")
async def create_conv(body: ConvIn, user=CurrentUser):
    if body.project_id:
        await assert_project(user["id"], body.project_id)
    c = {"id": new_id(), "user_id": user["id"], **body.model_dump(), "messages": [], "created_at": now_iso(), "updated_at": now_iso()}
    await db.conversations.insert_one(dict(c))
    c.pop("_id", None)
    return c


@api.get("/conversations/{cid}")
async def get_conv(cid: str, user=CurrentUser):
    c = await db.conversations.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Conversation not found")
    return c


@api.delete("/conversations/{cid}")
async def delete_conv(cid: str, user=CurrentUser):
    await db.conversations.delete_one({"id": cid, "user_id": user["id"]})
    return {"ok": True}


@api.post("/conversations/{cid}/messages")
async def send_message(cid: str, body: MsgIn, user=CurrentUser):
    uid = user["id"]
    conv = await get_conv(cid, user)
    if body.mode != "auto" and body.mode not in MODES:
        raise HTTPException(400, "Unknown mode")
    mode = body.mode if body.mode != "auto" else route_mode(body.content)
    auto = body.mode == "auto"
    settings = await get_settings(uid)
    context, n_papers = await build_context(uid, conv.get("project_id"), mode, body.content)
    history = "\n\n".join(f"{m['role'].upper()}: {m['content'][:3000]}" for m in conv["messages"][-10:])
    prompt = (f"{context}\n\nCONVERSATION SO FAR:\n{history or '(none)'}\n\nUSER: {body.content}\n\n"
              f"Answer the user. For each paper used, state whether full text or only metadata/abstract was available.")
    user_msg = {"id": new_id(), "role": "user", "content": body.content, "created_at": now_iso()}
    title = conv["title"] if conv["messages"] else body.content[:60]
    await db.conversations.update_one({"id": cid, "user_id": uid}, {"$push": {"messages": user_msg}, "$set": {"title": title, "updated_at": now_iso()}})

    async def gen():
        yield f"data: {json.dumps({'type': 'meta', 'mode': mode, 'mode_label': MODES[mode]['label'], 'auto': auto, 'papers_in_context': n_papers})}\n\n"
        parts = []
        try:
            async for t in llm.stream(settings["model"], system_prompt(mode), prompt):
                parts.append(t)
                yield f"data: {json.dumps({'type': 'delta', 'text': t})}\n\n"
        except Exception as e:
            msg = str(e) if isinstance(e, llm.LLMUnavailable) else f"AI model error: {str(e)[:200]}"
            yield f"data: {json.dumps({'type': 'error', 'error': msg})}\n\n"
            return
        a = {"id": new_id(), "role": "assistant", "content": "".join(parts), "mode": mode, "mode_label": MODES[mode]["label"],
             "papers_in_context": n_papers, "created_at": now_iso()}
        await db.conversations.update_one({"id": cid, "user_id": uid}, {"$push": {"messages": a}, "$set": {"updated_at": now_iso()}})
        yield f"data: {json.dumps({'type': 'done', 'message': a})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- Dashboard ----------
@api.get("/dashboard")
async def dashboard(user=CurrentUser):
    uid = user["id"]
    papers = await db.papers.find({"user_id": uid}, {"_id": 0, "year": 1, "sources": 1}).to_list(10000)
    by_year, by_source = {}, {}
    for p in papers:
        if p.get("year"):
            by_year[p["year"]] = by_year.get(p["year"], 0) + 1
        for s in p.get("sources") or []:
            by_source[s] = by_source.get(s, 0) + 1
    projects = await db.projects.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1).to_list(5)
    return {
        "projects": projects,
        "project_count": await db.projects.count_documents({"user_id": uid}),
        "paper_count": len(papers),
        "upload_count": await db.papers.count_documents({"user_id": uid, "origin": "upload"}),
        "note_count": await db.notes.count_documents({"user_id": uid}),
        "activity": await db.activity.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(10),
        "papers_by_year": [{"year": y, "count": c} for y, c in sorted(by_year.items())],
        "papers_by_source": [{"source": s, "count": c} for s, c in sorted(by_source.items(), key=lambda x: -x[1])],
    }


app.include_router(api)
from phase2 import router as phase2_router  # noqa: E402
app.include_router(phase2_router)
cors_origins = [origin.strip().rstrip("/") for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.login_attempts.create_index("identifier")
        for coll in ("projects", "papers", "notes", "conversations", "reports", "chunks", "activity"):
            await db[coll].create_index([("user_id", 1), ("id", 1)])
        await db.papers.create_index([("user_id", 1), ("project_ids", 1)])
        await db.chunks.create_index([("user_id", 1), ("paper_id", 1)])
        await db.settings.create_index("user_id", unique=True)
        await db.papers.update_many({"status": "processing"},
                                    {"$set": {"status": "profile_failed", "error": "Analysis was interrupted by a server restart. Please retry."}})
    except Exception as e:
        logging.getLogger("optinexus").error("MongoDB is not reachable or MONGO_URL/Atlas access is wrong: %s", e)


@app.on_event("shutdown")
async def shutdown():
    client.close()
