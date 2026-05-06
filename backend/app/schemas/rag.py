from uuid import UUID

from pydantic import BaseModel


class RagQuery(BaseModel):
    question: str
    top_k: int = 6
    coa_ids: list[UUID] | None = None  # restrict search to these CoAs


class RagCitation(BaseModel):
    coa_id: UUID
    chunk_id: UUID
    page: int | None
    score: float
    snippet: str
    doc_code: str | None
    batch_number: str | None


class RagAnswer(BaseModel):
    answer: str
    citations: list[RagCitation]
