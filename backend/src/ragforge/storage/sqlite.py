"""Small durable SQLite repository. SQL is deliberately parameterized."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

from ragforge.models import Chunk, Document


SCHEMA_VERSION = 1


class SQLiteStore:
    def __init__(self, path: str | Path = "ragforge.db") -> None:
        self.path = str(path)
        self._uri = self.path == ":memory:"
        if self._uri:
            # Shared in-memory DB keeps TestClient worker-thread connections coherent.
            self.path = "file:ragforge-shared-memory?mode=memory&cache=shared"
        self._local = threading.local()
        self._lock = threading.RLock()
        self._migrate()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False, uri=self._uri)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _migrate(self) -> None:
        conn = self._conn()
        with self._lock, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            version = int(row[0]) if row else 0
            if version < 1:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, text TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS chunks (
                        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        text TEXT NOT NULL, chunk_index INTEGER NOT NULL, start_char INTEGER NOT NULL,
                        end_char INTEGER NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, chunk_index);
                    DELETE FROM schema_version;
                    INSERT INTO schema_version(version) VALUES (1);
                """)

    @staticmethod
    def _doc(row: sqlite3.Row) -> Document:
        return Document(row["id"], row["title"], row["text"], json.loads(row["metadata"] or "{}"))

    @staticmethod
    def _chunk(row: sqlite3.Row) -> Chunk:
        return Chunk(row["id"], row["document_id"], row["text"], row["chunk_index"], row["start_char"], row["end_char"], json.loads(row["metadata"] or "{}"))

    def put_document(self, document: Document, chunks: Iterable[Chunk]) -> Document:
        conn = self._conn()
        with self._lock, conn:
            conn.execute("INSERT OR REPLACE INTO documents(id,title,text,metadata) VALUES (?,?,?,?)", (document.id, document.title, document.text, json.dumps(document.metadata)))
            conn.execute("DELETE FROM chunks WHERE document_id=?", (document.id,))
            conn.executemany("INSERT INTO chunks(id,document_id,text,chunk_index,start_char,end_char,metadata) VALUES (?,?,?,?,?,?,?)", [(c.id, c.document_id, c.text, c.index, c.start_char, c.end_char, json.dumps(c.metadata)) for c in chunks])
        return document

    def list_documents(self) -> list[Document]:
        return [self._doc(r) for r in self._conn().execute("SELECT * FROM documents ORDER BY created_at,id").fetchall()]

    def get_document(self, document_id: str) -> Document | None:
        r = self._conn().execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return self._doc(r) if r else None

    def get_chunks(self, document_ids: list[str] | None = None) -> list[Chunk]:
        if document_ids is None:
            rows = self._conn().execute("SELECT * FROM chunks ORDER BY document_id,chunk_index").fetchall()
        elif not document_ids:
            return []
        else:
            marks = ",".join("?" for _ in document_ids)
            rows = self._conn().execute(f"SELECT * FROM chunks WHERE document_id IN ({marks}) ORDER BY document_id,chunk_index", document_ids).fetchall()
        return [self._chunk(r) for r in rows]

    def delete_document(self, document_id: str) -> bool:
        conn = self._conn()
        with self._lock, conn:
            cur = conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
            return cur.rowcount > 0

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
