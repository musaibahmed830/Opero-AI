from fastapi import Query
from pydantic import BaseModel


class PageParams:
    """`Depends(PageParams)` — consistent pagination query params across every
    Phase 3 list endpoint (docs/API design: "consistent pagination").
    """

    def __init__(self, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
        self.page = page
        self.page_size = page_size

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
