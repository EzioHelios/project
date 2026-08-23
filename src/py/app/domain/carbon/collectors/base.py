"""Abstract data-acquisition adapter contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class IDataCollector(ABC):
    """Uniform data-acquisition adapter interface."""

    @abstractmethod
    async def connect(self) -> bool:
        """Open the upstream connection and report whether it is ready."""
        ...

    @abstractmethod
    async def fetch_data(self, **kwargs: Any) -> Any:
        """Fetch one raw payload from the upstream data source."""
        ...

    @abstractmethod
    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        """Normalize a raw payload into internal records."""
        ...

    @abstractmethod
    async def save(self, db_session: AsyncSession, normalized_list: list[dict[str, Any]]) -> int:
        """Persist normalized records and return the inserted count."""
        ...

    async def fetch_and_save(self, db_session: AsyncSession, **kwargs: Any) -> int:
        """Fetch, normalize and persist one upstream payload."""
        await self.connect()
        raw = await self.fetch_data(**kwargs)
        normalized = self.normalize(raw)
        if not normalized:
            return 0
        return await self.save(db_session, normalized)
