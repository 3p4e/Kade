from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession
from app.rag.llm import synthesize
from app.rag.retriever import retrieve
from app.schemas.rag import RagAnswer, RagCitation, RagQuery

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=RagAnswer)
async def ask(payload: RagQuery, session: DbSession, user: CurrentUserDep) -> RagAnswer:
    chunks = await retrieve(
        session,
        payload.question,
        top_k=max(1, min(20, payload.top_k)),
        coa_ids=payload.coa_ids,
    )
    answer = synthesize(payload.question, chunks)
    citations = [
        RagCitation(
            coa_id=c["coa_id"],
            chunk_id=c["chunk_id"],
            page=c.get("page"),
            score=float(c.get("score") or 0.0),
            snippet=(c["content"] or "")[:280],
            doc_code=c.get("doc_code"),
            batch_number=c.get("batch_number"),
        )
        for c in chunks
    ]
    return RagAnswer(answer=answer, citations=citations)
