"""采集适配器抽象基类 (IDataCollector)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class IDataCollector(ABC):
    """统一数据采集接口"""

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接（如创建 HTTP session、连接 MQTT broker 等）。
        返回 True 表示连接成功。
        """
        ...

    @abstractmethod
    async def fetch_data(self, **kwargs) -> Any:
        """从数据源拉取原始数据。
        返回原始接口响应（dict / list / bytes 等）。
        """
        ...

    @abstractmethod
    def normalize(self, raw: Any) -> list[dict]:
        """将原始响应标准化为我们内部格式的字典列表。
        每个字典对应一条待入库记录的字段键值对。
        """
        ...

    @abstractmethod
    async def save(self, db_session: AsyncSession, normalized_list: list[dict]) -> int:
        """将标准化后的数据批量写入数据库。
        返回写入条数。
        """
        ...

    async def fetch_and_save(self, db_session: AsyncSession, **kwargs) -> int:
        """模板方法：fetch_data -> normalize -> save 一气呵成。
        返回保存条数。
        """
        await self.connect()
        raw = await self.fetch_data(**kwargs)
        normalized = self.normalize(raw)
        if not normalized:
            return 0
        return await self.save(db_session, normalized)
