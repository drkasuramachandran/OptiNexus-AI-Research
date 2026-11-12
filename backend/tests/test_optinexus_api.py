"""OptiNexus API regression tests: auth, isolation, search, library, uploads, QA, notes, reports, chat SSE, settings."""
import json
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PDF_DIR = "/app/tests"
STATE = {}


def _register(prefix):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": f"TEST_{prefix}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["email"] == email and isinstance(d["token"], str)
    return {"Authorization": f"Bearer {d['token']}"}, d["user"]


@pytest.fixture(scope="module")
def u1():
    if "u1" not in STATE:
        STATE["u1"] = _register("a")
    return STATE["u1"][0]


@pytest.fixture(scope="module")
def u2():
    if "u2" not in STATE:
        STATE["u2"] = _register("b")
    return STATE["u2"][0]


@pytest.fixture(scope="module")
def projects(u1):
    a = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_Project A", "objectives": "obj"}).json()
    b = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_Project B"}).json()
    return a, b


# --- Auth ---
class TestAuth:
    def test_login_existing(self):
        r = requests.post(f"{API}/auth/login", json={"email": "t1@example.com", "password": "test123"})
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "t1@example.com"

    def test_me_and_unauth(self, u1):
        assert requests.get(f"{API}/auth/me", headers=u1).status_code == 200
        assert requests.get(f"{API}/auth/me").status_code == 401
        assert "password_hash" not in requests.get(f"{API}/auth/me", headers=u1).json()

    def test_duplicate_register(self, u1):
        email = STATE["u1"][1]["email"]
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "x"})
        assert r.status_code == 400


# --- Projects & isolation ---
class TestIsolation:
    def test_project_crud(self, u1, projects):
        a, _ = projects
        r = requests.put(f"{API}/projects/{a['id']}", headers=u1, json={"title": "TEST_Project A2"})
        assert r.status_code == 200 and r.json()["title"] == "TEST_Project A2"
        assert requests.get(f"{API}/projects/{a['id']}", headers=u1).json()["title"] == "TEST_Project A2"

    def test_cross_user_404(self, u1, u2, projects):
        a, _ = projects
        assert requests.get(f"{API}/projects/{a['id']}", headers=u2).status_code == 404
        assert requests.get(f"{API}/papers", headers=u2, params={"project_id": a["id"]}).status_code == 404
        assert requests.post(f"{API}/notes", headers=u2, json={"title": "x", "project_id": a["id"]}).status_code == 404
        assert requests.get(f"{API}/reports", headers=u2, params={"project_id": a["id"]}).status_code == 404

    def test_paper_scoped_to_project(self, u1, u2, projects):
        a, b = projects
        r = requests.post(f"{API}/papers", headers=u1, json={"title": "TEST_Paper only in A", "year": 2020, "project_id": a["id"], "sources": ["OpenAlex"]})
        assert r.status_code == 200
        pid = r.json()["id"]
        STATE["paperA"] = pid
        ids_a = [p["id"] for p in requests.get(f"{API}/papers", headers=u1, params={"project_id": a["id"]}).json()]
        ids_b = [p["id"] for p in requests.get(f"{API}/papers", headers=u1, params={"project_id": b["id"]}).json()]
        assert pid in ids_a and pid not in ids_b
        assert requests.get(f"{API}/papers/{pid}", headers=u2).status_code == 404
        assert requests.delete(f"{API}/papers/{pid}", headers=u2).status_code == 404
        # dedupe on re-save
        r2 = requests.post(f"{API}/papers", headers=u1, json={"title": "TEST_Paper only in A", "year": 2020, "project_id": b["id"]})
        assert r2.json()["id"] == pid and r2.json().get("already_saved")

    def test_notes_scoped(self, u1, u2, projects):
        a, b = projects
        n = requests.post(f"{API}/notes", headers=u1, json={"title": "TEST_note", "content": "c", "project_id": a["id"]}).json()
        assert n["id"] in [x["id"] for x in requests.get(f"{API}/notes", headers=u1, params={"project_id": a["id"]}).json()]
        assert n["id"] not in [x["id"] for x in requests.get(f"{API}/notes", headers=u1, params={"project_id": b["id"]}).json()]
        assert requests.put(f"{API}/notes/{n['id']}", headers=u2, json={"title": "hack"}).status_code == 404
        r = requests.put(f"{API}/notes/{n['id']}", headers=u1, json={"title": "TEST_note2", "content": "z"})
        assert r.status_code == 200 and r.json()["title"] == "TEST_note2"
        assert requests.delete(f"{API}/notes/{n['id']}", headers=u1).status_code == 200
        assert n["id"] not in [x["id"] for x in requests.get(f"{API}/notes", headers=u1).json()]


# --- Literature search ---
class TestSearch:
    def test_search_merged(self, u1):
        r = requests.post(f"{API}/search", headers=u1, json={"query": "fibre optic interferometric sensing"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        print("source status:", d["sources"], "results", len(d["results"]), "raw", d["raw_count"])
        assert set(d["sources"]) == {"openalex", "crossref", "arxiv", "pubmed"}
        assert len(d["results"]) > 0 and len(d["results"]) <= d["raw_count"]
        keys = [p["doi"] for p in d["results"] if p.get("doi")]
        assert len(keys) == len(set(keys)), "duplicate DOIs in merged results"

    def test_disable_source(self, u1):
        r = requests.put(f"{API}/settings", headers=u1, json={"sources": {"openalex": True, "crossref": True, "arxiv": False, "pubmed": True}})
        assert r.status_code == 200 and r.json()["sources"]["arxiv"] is False
        d = requests.post(f"{API}/search", headers=u1, json={"query": "fiber bragg grating"}, timeout=60).json()
        assert "arxiv" in d["disabled"] and "arxiv" not in d["sources"]
        requests.put(f"{API}/settings", headers=u1, json={"sources": {k: True for k in ["openalex", "crossref", "arxiv", "pubmed"]}})

    def test_settings_model_keys(self, u1):
        s = requests.get(f"{API}/settings", headers=u1).json()
        assert all(k["status"] in ("configured", "missing") for k in s["keys"])
        assert not any("value" in k for k in s["keys"])
        assert requests.put(f"{API}/settings", headers=u1, json={"model": "bogus"}).status_code == 400
        r = requests.put(f"{API}/settings", headers=u1, json={"model": "anthropic:claude-haiku-5-5"})
        assert r.json()["model"] == "anthropic:claude-haiku-5-5"
        requests.put(f"{API}/settings", headers=u1, json={"model": "anthropic:claude-sonnet-5-5"})


# --- Upload + QA ---
class TestUploadQA:
    def test_reject_non_pdf(self, u1):
        r = requests.post(f"{API}/papers/upload", headers=u1, files=[("files", ("notes.txt", b"hello world", "text/plain"))])
        assert r.status_code == 200 and r.json()["results"][0]["ok"] is False
        r = requests.post(f"{API}/papers/upload", headers=u1, files=[("files", ("fake.pdf", b"not a pdf at all", "application/pdf"))])
        assert r.json()["results"][0]["ok"] is False

    def test_upload_and_profile(self, u1, projects):
        a, _ = projects
        files = [("files", (n, open(f"{PDF_DIR}/{n}", "rb"), "application/pdf")) for n in ("fbg_strain_sensor.pdf", "mzi_temperature_sensor.pdf")]
        r = requests.post(f"{API}/papers/upload", headers=u1, files=files, data={"project_id": a["id"]}, timeout=60)
        assert r.status_code == 200
        res = r.json()["results"]
        assert all(x["ok"] for x in res), res
        ids = [x["paper_id"] for x in res]
        STATE["uploads"] = ids
        deadline = time.time() + 120
        while time.time() < deadline:
            st = [requests.get(f"{API}/papers/{i}", headers=u1).json() for i in ids]
            if all(p["status"] != "processing" for p in st):
                break
            time.sleep(5)
        for p in st:
            print(p["filename"], p["status"], p.get("error"), {k: (v[:50] if isinstance(v, str) else v) for k, v in (p.get("profile") or {}).items()})
            assert p["status"] == "ready", p.get("error")
            assert set(p["profile"]) >= {"title", "methods", "results", "doi"}

    def test_qa_with_citations(self, u1, projects):
        a, _ = projects
        r = requests.post(f"{API}/qa", headers=u1, json={"question": "What strain sensitivity was measured for the FBG sensor?", "project_id": a["id"]}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        print(json.dumps(d)[:800])
        assert d["evidence_found"] is True and d["citations"]
        c = d["citations"][0]
        assert c["document"].endswith(".pdf") and isinstance(c["page"], int) and c["excerpt"]

    def test_qa_nonsense(self, u1, projects):
        a, _ = projects
        r = requests.post(f"{API}/qa", headers=u1, json={"question": "What is the recipe for chocolate banana pancakes?", "project_id": a["id"]}, timeout=120)
        assert r.status_code == 200
        assert r.json()["evidence_found"] is False
        assert "No supporting evidence found" in r.json()["answer"]

    def test_qa_cross_user(self, u2, projects):
        a, _ = projects
        assert requests.post(f"{API}/qa", headers=u2, json={"question": "strain sensitivity", "project_id": a["id"]}).status_code == 404
        if STATE.get("uploads"):
            r = requests.post(f"{API}/qa", headers=u2, json={"question": "strain sensitivity", "paper_id": STATE["uploads"][0]})
            assert r.status_code == 400  # no uploaded PDFs in scope for user2


# --- Chat SSE + reports ---
def _chat(headers, cid, content, mode):
    r = requests.post(f"{API}/conversations/{cid}/messages", headers=headers, json={"content": content, "mode": mode}, stream=True, timeout=180)
    assert r.status_code == 200
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestChat:
    @pytest.mark.parametrize("mode,msg", [("literature_review", "Summarise the papers briefly in 3 bullet points."),
                                          ("gap_discovery", "List 2 research gaps briefly."),
                                          ("auto", "Compare the two sensors briefly.")])
    def test_modes(self, u1, projects, mode, msg):
        a, _ = projects
        c = requests.post(f"{API}/conversations", headers=u1, json={"project_id": a["id"]}).json()
        ev = _chat(u1, c["id"], msg, mode)
        types = [e["type"] for e in ev]
        print(mode, types[:3], types[-1], ev[0], [e.get("error") for e in ev if e["type"] == "error"])
        assert types[0] == "meta" and "delta" in types and types[-1] == "done"
        if mode == "auto":
            assert ev[0]["auto"] is True and ev[0]["mode"] == "paper_comparison"
        else:
            assert ev[0]["mode"] == mode
        conv = requests.get(f"{API}/conversations/{c['id']}", headers=u1).json()
        assert len(conv["messages"]) == 2 and conv["messages"][1]["role"] == "assistant"
        STATE["conv"] = conv
        assert c["id"] not in [x["id"] for x in requests.get(f"{API}/conversations", headers=u1, params={"project_id": projects[1]["id"]}).json()]

    def test_report(self, u1, u2, projects):
        a, b = projects
        r = requests.post(f"{API}/reports", headers=u1, json={"title": "TEST_report", "content": "abc", "project_id": a["id"]})
        assert r.status_code == 200
        assert r.json()["id"] in [x["id"] for x in requests.get(f"{API}/reports", headers=u1, params={"project_id": a["id"]}).json()]
        assert requests.post(f"{API}/reports", headers=u2, json={"title": "x", "content": "y", "project_id": a["id"]}).status_code == 404

    def test_dashboard(self, u1):
        d = requests.get(f"{API}/dashboard", headers=u1).json()
        assert d["project_count"] >= 2 and d["paper_count"] >= 1 and isinstance(d["papers_by_source"], list)
        with open("/tmp/onx_state.json", "w") as f:
            json.dump({"u1": STATE["u1"], "u2": STATE["u2"]}, f)
