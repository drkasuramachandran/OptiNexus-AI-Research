"""OptiNexus Phase 2 API tests: citations + Crossref verify, structured gaps, paper comparison, writing studio, docx, isolation.
Run serially: pytest /app/backend/tests/test_phase2_api.py -n 0
"""
import io
import os
import re
import time
import uuid
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PDF_DIR = "/app/tests"
S = {}
DOI = "10.1109/50.618377"  # Kersey et al. 1997, Fiber grating sensors, J. Lightwave Technol.


def _register(prefix):
    email = f"test_p2{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": f"TEST_{prefix}"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def env():
    if S:
        return S
    u1, u2 = _register("a"), _register("b")
    pa = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_P2 A", "objectives": "Optical fibre sensing of strain and temperature"}).json()
    pb = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_P2 B"}).json()
    pe = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_P2 Empty"}).json()
    p2 = requests.post(f"{API}/projects", headers=u2, json={"title": "TEST_P2 Other"}).json()
    files = [("files", (n, open(f"{PDF_DIR}/{n}", "rb"), "application/pdf")) for n in ("fbg_strain_sensor.pdf", "mzi_temperature_sensor.pdf")]
    up = requests.post(f"{API}/papers/upload", headers=u1, files=files, data={"project_id": pa["id"]}, timeout=60).json()["results"]
    uploads = [x["paper_id"] for x in up]
    # real crossref metadata for DOI paper
    m = requests.get(f"https://api.crossref.org/works/{DOI}", timeout=20).json()["message"]
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", [])]
    good = requests.post(f"{API}/papers", headers=u1, json={"title": m["title"][0], "authors": authors, "year": m["issued"]["date-parts"][0][0],
                                                           "journal": m["container-title"][0], "doi": DOI, "abstract": "FBG sensors review.", "project_id": pa["id"]}).json()
    bad = requests.post(f"{API}/papers", headers=u1, json={"title": "TEST_Totally different title", "authors": ["Jane Wrongname"], "year": 2015,
                                                          "journal": "Nature", "doi": "10.1364/OE.18.019844", "project_id": pb["id"]}).json()
    other = requests.post(f"{API}/papers", headers=u2, json={"title": "TEST_u2 paper", "authors": ["A B"], "year": 2020, "project_id": p2["id"]}).json()
    deadline = time.time() + 150
    while time.time() < deadline:
        st = [requests.get(f"{API}/papers/{i}", headers=u1).json()["status"] for i in uploads]
        if all(s != "processing" for s in st):
            break
        time.sleep(5)
    S.update(u1=u1, u2=u2, pa=pa, pb=pb, pe=pe, p2=p2, uploads=uploads, good=good, bad=bad, other=other)
    return S


# --- Citations ---
class TestCitations:
    def test_all_styles(self, env):
        r = requests.get(f"{API}/papers/{env['good']['id']}/citations", headers=env["u1"])
        assert r.status_code == 200
        f = r.json()["formats"]
        assert set(f) == {"APA", "IEEE", "Vancouver", "Harvard", "BibTeX", "RIS"}
        for k, v in f.items():
            print(k, "=>", v)
        assert "Kersey" in f["APA"] and "(1997)" in f["APA"] and f"https://doi.org/{DOI}" in f["APA"]
        assert f["BibTeX"].startswith("@article{") and f"doi = {{{DOI}}}" in f["BibTeX"]
        assert f["RIS"].startswith("TY  - JOUR") and f["RIS"].endswith("ER  - ")

    def test_verify_good(self, env):
        r = requests.post(f"{API}/papers/{env['good']['id']}/verify", headers=env["u1"], timeout=30).json()
        print(r)
        assert r["status"] == "verified", r
        assert len(r["checks"]) == 4 and all(c["match"] for c in r["checks"])
        # persisted
        assert requests.get(f"{API}/papers/{env['good']['id']}/citations", headers=env["u1"]).json()["verification"]["status"] == "verified"

    def test_verify_mismatch(self, env):
        r = requests.post(f"{API}/papers/{env['bad']['id']}/verify", headers=env["u1"], timeout=30).json()
        print(r)
        assert r["status"] in ("mismatch", "not_found"), r
        if r["status"] == "mismatch":
            assert any(not c["match"] for c in r["checks"])

    def test_verify_no_doi_upload(self, env):
        r = requests.post(f"{API}/papers/{env['uploads'][0]}/verify", headers=env["u1"]).json()
        assert r["status"] == "no_doi" and r["checks"] == []

    def test_citations_cross_user(self, env):
        assert requests.get(f"{API}/papers/{env['good']['id']}/citations", headers=env["u2"]).status_code == 404
        assert requests.post(f"{API}/papers/{env['good']['id']}/verify", headers=env["u2"]).status_code == 404


# --- Compare ---
class TestCompare:
    def test_validation(self, env):
        u1, pa = env["u1"], env["pa"]
        assert requests.post(f"{API}/compare", headers=u1, json={"project_id": pa["id"], "paper_ids": [env["uploads"][0]]}).status_code in (400, 422)
        assert requests.post(f"{API}/compare", headers=u1, json={"project_id": pa["id"], "paper_ids": [str(i) for i in range(7)]}).status_code in (400, 422)
        # duplicate id deduped -> only 1 valid
        assert requests.post(f"{API}/compare", headers=u1, json={"project_id": pa["id"], "paper_ids": [env["uploads"][0]] * 2}).status_code == 400
        # 1 valid + other project paper + other user's paper -> excluded -> 400
        r = requests.post(f"{API}/compare", headers=u1, json={"project_id": pa["id"], "paper_ids": [env["uploads"][0], env["bad"]["id"], env["other"]["id"]]})
        assert r.status_code == 400, r.text

    def test_cross_user_project(self, env):
        r = requests.post(f"{API}/compare", headers=env["u2"], json={"project_id": env["pa"]["id"], "paper_ids": env["uploads"]})
        assert r.status_code == 404

    def test_compare_run(self, env):
        ids = env["uploads"] + [env["good"]["id"], env["other"]["id"]]
        r = requests.post(f"{API}/compare", headers=env["u1"], json={"project_id": env["pa"]["id"], "paper_ids": ids}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["fields"] == ["objectives", "methodology", "instruments", "parameters", "conditions", "results", "limitations"]
        assert [x["paper_id"] for x in d["rows"]] == ids[:3]
        for row in d["rows"]:
            print(row["title"], row["basis"], {f: row[f][:60] for f in d["fields"]})
            assert all(isinstance(row[f], str) and row[f] for f in d["fields"])
        assert d["rows"][0]["basis"] == "full text" and d["rows"][2]["basis"] == "abstract + metadata"


# --- Structured gaps ---
class TestGaps:
    def test_empty_scope(self, env):
        c = requests.post(f"{API}/conversations", headers=env["u1"], json={"project_id": env["pe"]["id"]}).json()
        r = requests.post(f"{API}/conversations/{c['id']}/gaps", headers=env["u1"])
        assert r.status_code == 400 and "No papers" in r.json()["detail"]

    def test_cross_user(self, env):
        c = requests.post(f"{API}/conversations", headers=env["u1"], json={"project_id": env["pa"]["id"]}).json()
        S["conv_a"] = c["id"]
        assert requests.post(f"{API}/conversations/{c['id']}/gaps", headers=env["u2"]).status_code == 404

    def test_project_gaps(self, env):
        cid = S["conv_a"]
        r = requests.post(f"{API}/conversations/{cid}/gaps", headers=env["u1"], timeout=180)
        assert r.status_code == 200, r.text
        g = r.json()["messages"][1]["gaps"]
        print(g)
        assert g["papers_analysed"] == 3 and g["full_text_count"] == 2
        assert 1 <= len(g["items"]) <= 6
        valid = set(env["uploads"] + [env["good"]["id"]])
        for it in g["items"]:
            assert it["tag"] in ("Directly reported limitation", "Pattern inferred across studies", "AI suggestion")
            assert it["evidence_strength"] in ("Low", "Medium", "High")
            assert all(p["id"] in valid for p in it["supporting_papers"])
            if it["tag"] == "Pattern inferred across studies":
                assert len(it["supporting_papers"]) >= 2
        conv = requests.get(f"{API}/conversations/{cid}", headers=env["u1"]).json()
        assert conv["messages"][-1]["gaps"]["papers_analysed"] == 3
        assert conv["title"] == "Structured gap analysis"

    def test_library_gaps(self, env):
        c = requests.post(f"{API}/conversations", headers=env["u1"], json={}).json()
        r = requests.post(f"{API}/conversations/{c['id']}/gaps", headers=env["u1"], timeout=180)
        assert r.status_code == 200, r.text
        assert r.json()["messages"][1]["gaps"]["papers_analysed"] == 4  # 2 uploads + good + bad, not u2's


# --- Writing studio ---
class TestWriting:
    def test_validation_and_isolation(self, env):
        u1, pa = env["u1"], env["pa"]
        assert requests.post(f"{API}/writing/draft", headers=u1, json={"project_id": pa["id"], "paper_ids": env["uploads"], "doc_type": "x", "style": "APA"}).status_code == 400
        assert requests.post(f"{API}/writing/draft", headers=u1, json={"project_id": pa["id"], "paper_ids": env["uploads"], "doc_type": "abstract", "style": "BibTeX"}).status_code == 400
        assert requests.post(f"{API}/writing/draft", headers=env["u2"], json={"project_id": pa["id"], "paper_ids": env["uploads"], "doc_type": "abstract", "style": "APA"}).status_code == 404
        assert requests.post(f"{API}/writing/draft", headers=u1, json={"project_id": pa["id"], "paper_ids": [env["bad"]["id"], env["other"]["id"]], "doc_type": "abstract", "style": "APA"}).status_code == 400

    @pytest.mark.parametrize("style", ["APA", "IEEE"])
    def test_draft(self, env, style):
        ids = [env["uploads"][0], env["good"]["id"], env["bad"]["id"]]
        r = requests.post(f"{API}/writing/draft", headers=env["u1"], json={"project_id": env["pa"]["id"], "paper_ids": ids,
                                                                          "doc_type": "literature_review", "style": style, "instructions": "short, 2 paragraphs"}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        md = d["markdown"]
        print(style, d["unsupported_count"], d["cited"], d["uncited"])
        print(md[-1500:])
        assert "TEST_Totally different title" not in md  # other-project paper excluded
        assert not re.search(r"\[R\d", md)
        assert d["unsupported_count"] == len(re.findall(r"\[UNSUPPORTED", md))
        assert set(d["cited"]) | set(d["uncited"]) == {requests.get(f"{API}/papers/{i}", headers=env["u1"]).json()["title"] for i in ids[:2]}
        if d["cited"]:
            assert "## References" in md
            refs = md.split("## References", 1)[1]
            assert len([x for x in refs.strip().split("\n\n") if x.strip()]) == len(d["cited"])
            if style == "IEEE":
                assert re.search(r"\[\d+\]", md.split("## References")[0]) and refs.strip().startswith("[1]")
            else:
                assert re.search(r"\([A-Z][^()]*, (\d{4}|n\.d\.)\)", md.split("## References")[0])

    def test_docx(self, env):
        md = "# Title\n\nSome **bold** text (Kersey et al., 1997) [UNSUPPORTED].\n\n- item one\n1. numbered\n\n## References\n\nKersey, A. D. (1997)."
        r = requests.post(f"{API}/writing/docx", headers=env["u1"], json={"title": "Literature review draft", "markdown": md})
        assert r.status_code == 200
        assert "wordprocessingml" in r.headers["content-type"]
        assert 'filename="Literature_review_draft.docx"' in r.headers["content-disposition"]
        z = zipfile.ZipFile(io.BytesIO(r.content))
        xml = z.read("word/document.xml").decode()
        assert "Some " in xml and "bold" in xml and "UNSUPPORTED" in xml
        assert requests.post(f"{API}/writing/docx", json={"markdown": md}).status_code == 401
