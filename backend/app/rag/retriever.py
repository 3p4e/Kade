"""Vector retrieval over coa_chunks with optional CoA filter."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from .embedder import embed_one


async def retrieve(
    session: AsyncSession,
    question: str,
    *,
    top_k: int = 6,
    coa_ids: list[UUID] | None = None,
) -> list[dict]:
    qv = embed_one(question)
    # pgvector expects "[v1,v2,...]" string when bound as text
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in qv) + "]"

    if coa_ids:
        sql = text(
            """
            SELECT c.id           AS chunk_id,
                   c.coa_id       AS coa_id,
                   c.page         AS page,
                   c.content      AS content,
                   1 - (c.embedding <=> CAST(:vec AS vector)) AS score,
                   coa.doc_code   AS doc_code,
                   coa.batch_number AS batch_number
            FROM coa_chunks c
            JOIN coas coa ON coa.id = c.coa_id
            WHERE c.embedding IS NOT NULL
              AND c.coa_id IN :coa_ids
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        ).bindparams(bindparam("coa_ids", expanding=True))
        rows = await session.execute(sql, {"vec": vec_literal, "coa_ids": list(coa_ids), "k": top_k})
    else:
        sql = text(
            """
            SELECT c.id           AS chunk_id,
                   c.coa_id       AS coa_id,
                   c.page         AS page,
                   c.content      AS content,
                   1 - (c.embedding <=> CAST(:vec AS vector)) AS score,
                   coa.doc_code   AS doc_code,
                   coa.batch_number AS batch_number
            FROM coa_chunks c
            JOIN coas coa ON coa.id = c.coa_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        )
        rows = await session.execute(sql, {"vec": vec_literal, "k": top_k})

    return [dict(r._mapping) for r in rows]
