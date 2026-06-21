"""检索路由 —— 新闻向量检索"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_news_retriever
from schemas.requests import SearchNewsRequest
from schemas.responses import SearchNewsResponse, NewsItem
from core.exceptions import EventSandboxError
from infrastructure.retrieval.news_retriever import NewsRetriever

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["retrieval"])


@router.post("/news/search", response_model=SearchNewsResponse)
async def search_news(
    request: SearchNewsRequest,
    retriever: NewsRetriever = Depends(get_news_retriever),
):
    """根据文本检索相关新闻"""
    logger.info("[API] POST /api/news/search, query=%s...", request.query[:50])
    try:
        raw_results = await retriever.search(request.query, record_num=request.topk)

        items = []
        for r in raw_results:
            items.append(NewsItem(
                title=str(r.get("TRS_EventTitle", "")),
                time=str(r.get("TRS_EventTimeOriWord", "")),
                keywords=str(r.get("TRS_EventKeywords", "")),
                description=str(r.get("TRS_EventDescription", "")),
            ))

        return SearchNewsResponse(
            query=request.query,
            total=len(items),
            results=items,
        )
    except EventSandboxError as e:
        logger.warning("[API] 业务异常: %s", e.message)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error("[API] 检索异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"检索失败: {e}")
