import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

def _need(name):
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(
            f"Missing setting {name}. Copy backend/.env.example to backend/.env and fill it in "
            f"(on Render, add it under Environment)."
        )
    return v


_mongo_url = _need("MONGO_URL")
if "USERNAME:PASSWORD" in _mongo_url or "YOUR-CLUSTER" in _mongo_url:
    raise RuntimeError("MONGO_URL in backend/.env is still the example placeholder. Paste your real MongoDB connection string.")
_need("JWT_SECRET")
client = AsyncIOMotorClient(_mongo_url, serverSelectionTimeoutMS=10000)
db = client[os.environ.get("DB_NAME", "optinexus")]

JWT_ALGORITHM = "HS256"
DEFAULT_MODEL = "gemini:gemini-3.8-flash"
SOURCES = ["openalex", "crossref", "arxiv", "pubmed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


CurrentUser = Depends(get_current_user)


async def get_settings(user_id: str) -> dict:
    s = await db.settings.find_one({"user_id": user_id}, {"_id": 0})
    if not s:
        s = {"user_id": user_id, "model": DEFAULT_MODEL, "sources": {k: True for k in SOURCES}}
        await db.settings.insert_one(dict(s))
    elif s.get("model") not in {"gemini:gemini-2.5-flash", "gemini:gemini-2.5-pro"}:
        # Migrate legacy Emergent/provider model IDs to the independent Gemini default.
        await db.settings.update_one({"user_id": user_id}, {"$set": {"model": DEFAULT_MODEL}})
        s["model"] = DEFAULT_MODEL
    return s


async def assert_project(user_id: str, project_id: str) -> dict:
    p = await db.projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    return p


async def log_activity(user_id: str, text: str, kind: str = "info"):
    await db.activity.insert_one({"id": new_id(), "user_id": user_id, "text": text, "kind": kind, "created_at": now_iso()})
