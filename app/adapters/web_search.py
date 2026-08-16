from abc import ABC, abstractmethod
from dataclasses import dataclass

from ddgs import DDGS


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearch(ABC):
    @abstractmethod
    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]: ...


class DuckDuckGoSearch(WebSearch):
    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        # A failed search is a soft miss (return nothing), never a crash — the
        # caller (nutrition fallback or chat tool) degrades gracefully.
        try:
            rows = DDGS().text(query, max_results=max_results)
        except Exception:
            return []
        return [
            SearchResult(
                title=row.get("title") or "",
                url=row.get("href") or "",
                snippet=row.get("body") or "",
            )
            for row in rows
        ]
