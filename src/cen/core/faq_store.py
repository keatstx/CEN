"""SQLite-backed FAQ store + lightweight TF-IDF retrieval.

The retrieval uses a stdlib-only TF-IDF + cosine similarity scheme
that's good enough for the small FAQ corpora we expect (dozens to a
few hundred entries per project/module). It is intentionally NOT
sentence-transformers — that would add a heavy dep, a model download,
and CPU init lag. The retrieval interface is small enough that we can
swap in a real embedding backend later behind the same surface.

Per CLAUDE.md non-negotiable #1, the question text the user types is
PII-scrubbed before it ever reaches this layer.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from cen.core.models import FAQ


# Tokenizer used by both indexing and querying. Lowercase, alpha-only,
# strip very short and very common stopwords.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "i", "you", "he", "she",
    "it", "we", "they", "this", "that", "these", "those", "my", "your",
    "his", "her", "its", "our", "their", "if", "as", "by", "from",
}
_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z']+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if len(t) > 2 and t.lower() not in _STOPWORDS]


def _vec(tokens: list[str]) -> Counter[str]:
    return Counter(tokens)


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class FAQStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS faqs (
                id TEXT PRIMARY KEY,
                module_name TEXT,
                project_id TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                source_filename TEXT NOT NULL DEFAULT '',
                owner_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_faqs_module ON faqs(module_name)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_faqs_project ON faqs(project_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_faqs_owner ON faqs(owner_id)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(
        self,
        question: str,
        answer: str,
        *,
        module_name: Optional[str] = None,
        project_id: Optional[str] = None,
        source_filename: str = "",
        owner_id: Optional[str] = None,
    ) -> FAQ:
        now = datetime.now(timezone.utc).isoformat()
        faq = FAQ(
            id=uuid.uuid4().hex,
            module_name=module_name,
            project_id=project_id,
            question=question,
            answer=answer,
            source_filename=source_filename,
            owner_id=owner_id,
            created_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO faqs
                (id, module_name, project_id, question, answer,
                 source_filename, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                faq.id,
                faq.module_name,
                faq.project_id,
                faq.question,
                faq.answer,
                faq.source_filename,
                faq.owner_id,
                faq.created_at,
            ),
        )
        await self._db.commit()
        return faq

    async def get(self, faq_id: str) -> FAQ | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM faqs WHERE id = ?", (faq_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_faq(row)

    async def list_all(
        self,
        *,
        module_name: Optional[str] = None,
        project_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> list[FAQ]:
        """List FAQs matching the given scope.

        Behavior:
        - When ``module_name`` or ``project_id`` is provided, returns
          the union of: FAQs matching that scope + globally-scoped
          FAQs (module_name IS NULL AND project_id IS NULL).
        - When BOTH module_name and project_id are None (typical
          for SOP Studio / Dashboard, where there's no active case),
          returns every FAQ the owner can see — module-scoped FAQs
          are still useful to surface, just not filtered to one. The
          previous behavior of "globals only" returned nothing when
          the library was use-case-scoped, which made the concierge
          inert outside the Executor.
        - ``owner_id`` is the multi-tenant filter (always applied).
        """
        assert self._db is not None
        clauses: list[str] = []
        params: list = []
        if module_name is not None or project_id is not None:
            scope: list[str] = ["(module_name IS NULL AND project_id IS NULL)"]
            if module_name is not None:
                scope.append("module_name = ?")
                params.append(module_name)
            if project_id is not None:
                scope.append("project_id = ?")
                params.append(project_id)
            clauses.append("(" + " OR ".join(scope) + ")")
        # else: no scope filter — return everything the owner can see.
        if owner_id is not None:
            clauses.append("(owner_id IS NULL OR owner_id = ?)")
            params.append(owner_id)
        where = " AND ".join(clauses) if clauses else "1=1"
        query = f"SELECT * FROM faqs WHERE {where} ORDER BY created_at DESC"
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_faq(row) for row in rows]

    async def delete(self, faq_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM faqs WHERE id = ?", (faq_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        module_name: Optional[str] = None,
        project_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> list[tuple[FAQ, float]]:
        """Return up to top_k FAQs ranked by cosine similarity against
        the query, filtered to scores >= min_score. Each result is a
        (FAQ, score) tuple. The score is informational; it's a TF-IDF
        cosine over a stdlib bag-of-words, not a real semantic embedding.
        """
        candidates = await self.list_all(
            module_name=module_name,
            project_id=project_id,
            owner_id=owner_id,
        )
        if not candidates:
            return []
        q_vec = _vec(_tokenize(query))
        if not q_vec:
            return []
        scored: list[tuple[FAQ, float]] = []
        for faq in candidates:
            # Index the question + first 200 chars of the answer so the
            # match works whether the user phrases their question close
            # to ours or close to the answer.
            doc_text = f"{faq.question} {faq.answer[:200]}"
            d_vec = _vec(_tokenize(doc_text))
            score = _cosine(q_vec, d_vec)
            if score >= min_score:
                scored.append((faq, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _row_to_faq(row: aiosqlite.Row) -> FAQ:
        return FAQ(
            id=row["id"],
            module_name=row["module_name"],
            project_id=row["project_id"],
            question=row["question"],
            answer=row["answer"],
            source_filename=row["source_filename"],
            owner_id=row["owner_id"],
            created_at=row["created_at"],
        )
