import math
import re
from collections import Counter

import fitz

MAX_BYTES = 20 * 1024 * 1024
CHUNK_CHARS = 1200
OVERLAP = 200
HEADING_RE = re.compile(
    r"^\s*((\d+(\.\d+)*\.?|[IVX]+\.)\s+)?(abstract|introduction|background|related work|theory|principle|methods?|"
    r"materials and methods|methodology|experimental( setup| section| details)?|experiments?|setup|results( and discussion)?|"
    r"discussion|conclusions?|future work|limitations|acknowledg(e)?ments?|references)\b[\s:.]*$", re.I)
STOP = set("the a an of and or to in on for with by is are was were be this that from as at it its we our can which these those".split())


class PDFError(Exception):
    pass


def extract_pages(data: bytes) -> list[str]:
    if not data.startswith(b"%PDF"):
        raise PDFError("File is not a valid PDF.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise PDFError("PDF could not be opened (corrupted or encrypted).")
    pages = [p.get_text("text") for p in doc]
    if sum(len(p.strip()) for p in pages) < 200:
        raise PDFError("No extractable text found. Only text-based PDFs are supported (scanned PDFs need OCR).")
    return pages


def chunk_pages(pages: list[str]) -> list[dict]:
    chunks, section = [], "Front matter"
    for pno, text in enumerate(pages, start=1):
        segments, buf, buf_section = [], [], section
        for line in text.splitlines():
            if HEADING_RE.match(line) and len(line) < 60:
                if buf:
                    segments.append((buf_section, " ".join(buf)))
                    buf = []
                section = buf_section = line.strip().rstrip(":.")
            buf.append(line.strip())
        if buf:
            segments.append((buf_section, " ".join(buf)))
        for sec, seg in segments:
            seg = re.sub(r"\s+", " ", seg).strip()
            start = 0
            while start < len(seg):
                piece = seg[start:start + CHUNK_CHARS]
                if len(piece) > 40:
                    chunks.append({"page": pno, "section": sec, "text": piece})
                start += CHUNK_CHARS - OVERLAP
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
    return chunks


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 1]


def bm25(query: str, chunks: list[dict], k: int = 12, per_paper: int = 5) -> list[dict]:
    q = set(tokens(query))
    seen, uniq = set(), []
    for c in chunks:
        if c["text"] not in seen:
            seen.add(c["text"])
            uniq.append(c)
    chunks = uniq
    if not q or not chunks:
        return []
    docs = [Counter(tokens(c["text"])) for c in chunks]
    n, avg = len(docs), sum(sum(d.values()) for d in docs) / max(len(docs), 1)
    df = Counter(t for d in docs for t in q if t in d)
    scored = []
    for c, d in zip(chunks, docs):
        dl, s = sum(d.values()), 0.0
        for t in q:
            if t in d:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * d[t] * 2.5 / (d[t] + 1.5 * (0.25 + 0.75 * dl / avg))
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    out, counts = [], Counter()
    for _, c in scored:
        if counts[c.get("paper_id")] < per_paper:
            counts[c.get("paper_id")] += 1
            out.append(c)
        if len(out) >= k:
            break
    return out


def wrap_data(label: str, text: str) -> str:
    return (f"<<<BEGIN UNTRUSTED DATA: {label}>>>\n{text}\n<<<END UNTRUSTED DATA: {label}>>>")
