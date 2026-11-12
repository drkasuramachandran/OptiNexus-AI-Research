# OptiNexus AI — PRD
"Intelligence for Scientific Discovery". AI research workspace for scientists. Full original spec in first user message (8 pages, standing anti-fabrication rules, acceptance test).

## Choices
- LLM: Claude Sonnet 5.5 (anthropic:claude-sonnet-5-5) via Emergent LLM key; switchable in Settings (llm.py provider interface)
- PDFs: only extracted text kept (page + section chunks); original file discarded

## Architecture
- Backend FastAPI: core.py (db, JWT auth, settings), llm.py, literature.py (OpenAlex/Crossref/arXiv/PubMed parallel, merge+dedupe), documents.py (PyMuPDF extraction, chunking, BM25), agents.py (5 modes, standing rules, keyword orchestrator, context builder), server.py (routes)
- Frontend React: pages Dashboard, Projects(+detail tabs), Search, Library, Analyzer, Assistant, Notes, Settings
- Auth: JWT Bearer (localStorage), bcrypt, login lockout; every query filtered by user_id

## Implemented (2026-06)
- All 8 pages, SSE streaming chat, page-cited Q&A with verbatim excerpt verification, profile with "Not found in document", reports saved from project chats
- Fixes after test pass: retrieval dedupe + per-paper cap, upload dedupe by SHA-256, interrupted analyses become retryable, lockout expiry

## Implemented Phase 2 (2026-06)
- Structured gap discovery cards (Assistant, gap mode), project Compare tab with CSV, citation formats APA/IEEE/Vancouver/Harvard/BibTeX/RIS + Crossref DOI verification, Writing Studio (/writing) with project-only citations, [UNSUPPORTED] flags, MD/DOCX export, README

## Backlog
- P1: OCR for scanned PDFs; semantic (embedding) retrieval
- P2: export reports; citation styles
