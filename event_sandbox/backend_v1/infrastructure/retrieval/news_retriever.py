"""新闻向量检索服务。

封装 Hybase 向量检索与 bge-m3 Embedding 调用，
支持根据文本描述检索相关新闻报道。
"""

import asyncio
import json
import logging
from typing import Optional

import httpx

from core.config import get_settings
from .hybase_api import HybaseApi

logger = logging.getLogger(__name__)


class NewsRetriever:
    """新闻向量检索器"""

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.news_retrieval_enabled
        self.database = settings.news_hybase_database
        self.embedding_url = settings.news_embedding_url
        self.embedding_model = settings.news_embedding_model
        self.topk = settings.news_retrieval_topk

        # Hybase 配置（同步库，在线程池中调用）
        self._hybase_config = {
            "hybase_key": settings.news_hybase_key,
            "hybase_host": settings.news_hybase_host,
            "hybase_security_code": settings.news_hybase_security_code,
        }
        self._hydb = None

        # Embedding 异步客户端
        self._client = httpx.AsyncClient(timeout=30)

        if self.enabled and (not settings.news_hybase_key or not settings.news_hybase_host):
            logger.warning("[NewsRetriever] 新闻检索配置不完整，已自动禁用")
            self.enabled = False

        logger.info(
            "[NewsRetriever] 初始化完成, enabled=%s, db=%s, embedding=%s",
            self.enabled,
            self.database,
            self.embedding_url,
        )

    def _get_hydb(self):
        """延迟初始化 HybaseApi（同步对象，仅在线程池中访问）"""
        if self._hydb is None:
            try:
                self._hydb = HybaseApi(self._hybase_config)
            except Exception as e:
                logger.error("[NewsRetriever] HybaseApi 初始化失败: %s", e)
                raise
        return self._hydb

    async def _get_embedding(self, text: str) -> str:
        """获取文本的向量表示（逗号分隔的字符串）"""
        payload = {
            "input": text,
            "model": self.embedding_model,
        }
        try:
            resp = await self._client.post(self.embedding_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("[NewsRetriever] Embedding 请求失败: %s", e)
            raise

        if "data" not in data or not data["data"] or "embedding" not in data["data"][0]:
            logger.error("[NewsRetriever] Embedding 返回结构异常: %s", data)
            raise ValueError("Embedding API 返回数据异常")

        vector = data["data"][0]["embedding"]
        return ",".join(str(i) for i in vector)

    def _hybase_search_sync(
        self,
        query: str,
        return_fields: list[str],
        record_num: int,
        search_type: str,
        vector_query_field: str,
    ) -> tuple[list[dict], int]:
        """同步 Hybase 检索（供线程池调用）"""
        hydb = self._get_hydb()
        if search_type == "vector":
            result_set = hydb.hybase_vector_executeSelect(
                self.database,
                query,
                start=0,
                recordNum=record_num,
                vector_fields=vector_query_field,
            )
        else:
            result_set = hydb.hybase_executeSelect(
                self.database,
                query,
                start=0,
                recordNum=record_num,
            )

        results = []
        i = 0
        size = result_set.size()
        while i < size:
            result_set.moveNext()
            record = result_set.get()
            row = {}
            for field in return_fields:
                row[field] = record.getString(field)
            results.append(row)
            i += 1

        return results, size

    async def search(
        self,
        text: str,
        return_fields: Optional[list[str]] = None,
        record_num: Optional[int] = None,
    ) -> list[dict]:
        """根据文本检索相关新闻。

        Args:
            text: 查询文本（如事件描述）
            return_fields: 需要返回的字段列表，默认返回常用字段
            record_num: 返回条数上限，默认读取配置

        Returns:
            新闻列表，每条为 dict
        """
        if not self.enabled:
            logger.warning("[NewsRetriever] 新闻检索未启用")
            return []

        if not text or not text.strip():
            return []

        return_fields = return_fields or [
            "TRS_EventTitle",
            "TRS_EventTimeOriWord",
            "TRS_EventKeywords",
            "TRS_EventDescription",
        ]
        record_num = record_num or self.topk
        vector_query_field = "TRS_EventVector"

        # 1. 获取向量
        logger.info("[NewsRetriever] 开始获取 embedding, text=%s...", text[:50])
        vector_str = await self._get_embedding(text)
        if not vector_str:
            return []

        # 2. 构造 Hybase 查询语句
        query = f'{vector_query_field}: "{vector_str}"'
        logger.info("[NewsRetriever] 开始向量检索, db=%s, topk=%d", self.database, record_num)

        # 3. 在线程池中执行同步 Hybase 调用
        try:
            results, total = await asyncio.to_thread(
                self._hybase_search_sync,
                query,
                return_fields,
                record_num,
                "vector",
                vector_query_field,
            )
        except Exception as e:
            logger.error("[NewsRetriever] Hybase 检索失败: %s", e)
            return []

        logger.info("[NewsRetriever] 检索完成, results=%d, total=%d", len(results), total)
        return results

    async def close(self) -> None:
        """关闭异步客户端"""
        await self._client.aclose()
        logger.info("[NewsRetriever] 连接已关闭")
