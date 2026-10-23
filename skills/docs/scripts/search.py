#!/usr/bin/env python3
"""Local full-text search over the docs-reference library (SQLite FTS5).

Indexes <tool>/brief.md, <tool>/history.md and every *.md / *.txt / *.json
under <tool>/full/ (files over 5 MB and binary files are skipped). Text is
chunked by markdown heading, max ~2000 chars per chunk. The index lives at
<lib>/_state/search.db and is refreshed incrementally (mtime + size) on
every search.

Usage:
    search.py "<query>" [--tool T] [--limit 8] [--briefs-only] [--json]
    search.py "<query>" --raw      # pass query to FTS5 as-is (AND/OR/NEAR/prefix*)
    search.py --reindex            # drop and rebuild the whole index

By default each query word is quoted, so punctuation such as "dist-tags" or
"v2.1" cannot cause FTS syntax errors. Hits are ranked by bm25, with
brief.md hits boosted because they are curated.
Library root defaults to ~/docs-reference, override with
DOCS_REFERENCE_DIR.
"""
import os
import re
import sys
import json
import sqlite3
import argparse
from pathlib import Path

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))
MAX_BYTES = 5 * 1024 * 1024
MAX_CHUNK = 2000
BRIEF_BOOST = 1.6  # bm25 is negative; larger magnitude = better
SCHEMA = """
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY, tool TEXT, path TEXT, line INTEGER,
  heading TEXT, text TEXT, brief INTEGER);
CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
  heading, text, content='chunks', content_rowid='id',
  tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO fts(rowid, heading, text) VALUES (new.id, new.heading, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO fts(fts, rowid, heading, text) VALUES ('delete', old.id, old.heading, old.text);
END;
"""


def db_path():
    return LIB / "_state" / "search.db"


def connect():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    return con


def ensure_gitignore():
    gi = LIB / ".gitignore"
    try:
        lines = gi.read_text().splitlines() if gi.exists() else []
        if not any(l.strip() in ("_state/", "_state", "/_state/") for l in lines):
            with gi.open("a") as f:
                if lines and lines[-1].strip():
                    f.write("\n")
                f.write("# search index and other local state\n_state/\n")
    except OSError:
        pass


def tool_dirs():
    return sorted(d for d in LIB.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", ".")))


def candidate_files():
    for d in tool_dirs():
        for name in ("brief.md", "history.md"):
            p = d / name
            if p.is_file():
                yield d.name, p
        full = d / "full"
        if full.is_dir():
            for p in sorted(full.rglob("*")):
                if p.is_file() and p.suffix.lower() in (".md", ".txt", ".json"):
                    yield d.name, p


def read_text(p):
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def split_long(lines, start, heading):
    """Yield (line, text) pieces of at most ~MAX_CHUNK chars, split on lines."""
    buf, buf_start, size = [], start, 0
    for i, ln in enumerate(lines):
        # hard-split absurdly long lines (minified json etc.)
        parts = [ln[j:j + MAX_CHUNK] for j in range(0, len(ln), MAX_CHUNK)] or [""]
        for part in parts:
            if buf and size + len(part) + 1 > MAX_CHUNK:
                yield buf_start, "\n".join(buf)
                buf, size, buf_start = [], 0, start + i
            buf.append(part)
            size += len(part) + 1
    if buf:
        yield buf_start, "\n".join(buf)


def chunk_markdown(text):
    """Return list of (start_line, heading, text)."""
    out, heading, cur, cur_start = [], "", [], 1
    in_fence = False

    def flush():
        body = "\n".join(cur).strip()
        if body:
            for ln, piece in split_long(cur, cur_start, heading):
                if piece.strip():
                    out.append((ln, heading, piece))

    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"#{1,6}\s+(.*)", line)
        if m:
            flush()
            heading, cur, cur_start = m.group(1).strip(), [line], n
        else:
            cur.append(line)
    flush()
    return out


def index_file(con, tool, p):
    rel = str(p.relative_to(LIB))
    text = read_text(p)
    con.execute("DELETE FROM chunks WHERE path=?", (rel,))
    if text is None:
        return
    brief = 1 if p.name == "brief.md" else 0
    con.executemany(
        "INSERT INTO chunks(tool,path,line,heading,text,brief) VALUES (?,?,?,?,?,?)",
        [(tool, rel, ln, h, t, brief) for ln, h, t in chunk_markdown(text)])


def refresh(con, rebuild=False):
    """Incremental sync of the index. Returns (changed, removed)."""
    if rebuild:
        con.executescript("DELETE FROM chunks; DELETE FROM files;"
                          "INSERT INTO fts(fts) VALUES('rebuild');")
    known = {r[0]: (r[1], r[2]) for r in con.execute("SELECT path,mtime,size FROM files")}
    seen, changed = set(), 0
    for tool, p in candidate_files():
        rel = str(p.relative_to(LIB))
        seen.add(rel)
        try:
            st = p.stat()
        except OSError:
            continue
        if known.get(rel) == (st.st_mtime, st.st_size):
            continue
        index_file(con, tool, p)
        con.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)",
                    (rel, st.st_mtime, st.st_size))
        changed += 1
    gone = [r for r in known if r not in seen]
    for rel in gone:
        con.execute("DELETE FROM chunks WHERE path=?", (rel,))
        con.execute("DELETE FROM files WHERE path=?", (rel,))
    con.commit()
    return changed, len(gone)


def build_query(q, raw):
    if raw:
        return q
    words = [w for w in re.split(r"\s+", q.strip()) if w]
    return " ".join('"' + w.replace('"', '""') + '"' for w in words)


def search(con, q, tool=None, limit=8, briefs_only=False, raw=False, full=False):
    sql = ("SELECT c.tool, c.path, c.line, c.heading, c.brief, "
           "snippet(fts, 1, '[', ']', ' ... ', 32) AS snip, "
           + ("fts.text AS body, " if full else "") +
           "bm25(fts, 3.0, 1.0) * CASE c.brief WHEN 1 THEN ? ELSE 1.0 END AS score "
           "FROM fts JOIN chunks c ON c.id = fts.rowid WHERE fts MATCH ?")
    args = [BRIEF_BOOST, build_query(q, raw)]
    if tool:
        sql += " AND c.tool = ?"
        args.append(tool)
    if briefs_only:
        sql += " AND c.brief = 1"
    sql += " ORDER BY score LIMIT ?"
    args.append(limit)
    cols = ["tool", "path", "line", "heading", "brief", "snippet"] + (["text"] if full else []) + ["score"]
    return [dict(zip(cols, r)) for r in con.execute(sql, args)]


def main():
    ap = argparse.ArgumentParser(description="Search the docs-reference library.")
    ap.add_argument("query", nargs="?")
    ap.add_argument("--tool")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--briefs-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--full", action="store_true", help="with --json: include each hit's whole chunk text")
    ap.add_argument("--raw", action="store_true", help="raw FTS5 query syntax")
    ap.add_argument("--reindex", action="store_true", help="rebuild the index")
    a = ap.parse_args()
    if not a.query and not a.reindex:
        ap.error("give a query or --reindex")
    if not LIB.is_dir():
        sys.exit(f"library not found: {LIB}")
    ensure_gitignore()
    con = connect()
    changed, removed = refresh(con, rebuild=a.reindex)
    if a.reindex:
        n = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"indexed {changed} files, {n} chunks")
        if not a.query:
            return
    try:
        hits = search(con, a.query, a.tool, a.limit, a.briefs_only, a.raw, a.full)
    except sqlite3.OperationalError as e:
        sys.exit(f"query error: {e} (try without --raw)")
    if a.json:
        print(json.dumps(hits, indent=2))
        return
    if not hits:
        print("no hits")
    for h in hits:
        head = f"  [{h['heading']}]" if h["heading"] else ""
        print(f"{h['tool']}  {h['path']}:{h['line']}{head}")
        snip = re.sub(r"\s+", " ", h["snippet"]).strip()[:200]
        print(f"    {snip}")


if __name__ == "__main__":
    main()
