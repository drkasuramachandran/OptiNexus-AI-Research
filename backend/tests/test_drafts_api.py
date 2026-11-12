# Save Drafts feature: CRUD, per-project and per-user isolation
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _reg(p):
    r = requests.post(f"{API}/auth/register", json={"email": f"test_dr{p}_{uuid.uuid4().hex[:8]}@example.com", "password": "test123", "name": f"TEST_{p}"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def env():
    u1, u2 = _reg("a"), _reg("b")
    pa = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_DR A"}).json()
    pb = requests.post(f"{API}/projects", headers=u1, json={"title": "TEST_DR B"}).json()
    p2 = requests.post(f"{API}/projects", headers=u2, json={"title": "TEST_DR Other"}).json()
    yield dict(u1=u1, u2=u2, pa=pa["id"], pb=pb["id"], p2=p2["id"])
    for h, p in ((u1, pa), (u1, pb), (u2, p2)):
        requests.delete(f"{API}/projects/{p['id']}", headers=h)


def test_crud_and_isolation(env):
    u1, u2 = env["u1"], env["u2"]
    body = {"project_id": env["pa"], "title": "TEST_draft", "markdown": "# Hello", "doc_type": "review", "style": "ieee", "paper_ids": []}
    r = requests.post(f"{API}/drafts", headers=u1, json=body)
    assert r.status_code == 200, r.text
    d = r.json(); did = d["id"]
    assert d["title"] == "TEST_draft" and "_id" not in d
    lst = requests.get(f"{API}/drafts", headers=u1, params={"project_id": env["pa"]}).json()
    assert [x["id"] for x in lst] == [did]
    # update (no duplicate)
    r = requests.put(f"{API}/drafts/{did}", headers=u1, json={**body, "markdown": "# Edited"})
    assert r.status_code == 200 and r.json()["markdown"] == "# Edited"
    lst = requests.get(f"{API}/drafts", headers=u1, params={"project_id": env["pa"]}).json()
    assert len(lst) == 1 and lst[0]["markdown"] == "# Edited"
    # per project
    assert requests.get(f"{API}/drafts", headers=u1, params={"project_id": env["pb"]}).json() == []
    # validation
    assert requests.post(f"{API}/drafts", headers=u1, json={**body, "title": ""}).status_code == 422
    # per user
    assert requests.get(f"{API}/drafts", headers=u2, params={"project_id": env["pa"]}).status_code == 404
    assert requests.post(f"{API}/drafts", headers=u2, json=body).status_code == 404
    r = requests.put(f"{API}/drafts/{did}", headers=u2, json={**body, "project_id": env["p2"], "markdown": "HACK"})
    assert r.status_code == 404
    requests.delete(f"{API}/drafts/{did}", headers=u2)
    lst = requests.get(f"{API}/drafts", headers=u1, params={"project_id": env["pa"]}).json()
    assert len(lst) == 1 and lst[0]["markdown"] == "# Edited"
    # moving draft to project B via PUT (project_id is part of body)
    r = requests.put(f"{API}/drafts/{did}", headers=u1, json={**body, "project_id": env["pb"]})
    assert r.status_code == 200
    requests.put(f"{API}/drafts/{did}", headers=u1, json=body)
    # delete
    assert requests.delete(f"{API}/drafts/{did}", headers=u1).status_code == 200
    assert requests.get(f"{API}/drafts", headers=u1, params={"project_id": env["pa"]}).json() == []
    assert requests.put(f"{API}/drafts/{did}", headers=u1, json=body).status_code == 404
