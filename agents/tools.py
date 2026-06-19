"""
agents/tools.py — Bull/Bear 에이전트가 호출 가능한 도구 정의

[변경 사항 v2]
- search_web_news로 가져온 기사들을 세션 단위 컨테이너에 누적.
- orchestrator가 토론 시작 시 clear_session_articles()로 초기화하고,
  토론 끝에 get_session_articles()로 가져가 UI 결과에 합침.

[.env]
  NAVER_CLIENT_ID=...
  NAVER_CLIENT_SECRET=...
"""

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from rag.retriever import search as rag_search

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ═════════════════════════════════════════════════════════
# 세션 단위 수집 컨테이너 (토론 1회당 비우고 채움)
# ═════════════════════════════════════════════════════════
_session_articles: list[dict] = []


def clear_session_articles() -> None:
    """토론 시작 시 호출 — 컨테이너 비우기."""
    _session_articles.clear()


def get_session_articles() -> list[dict]:
    """현재 세션 동안 tool로 가져온 article 리스트 (복사본)."""
    return list(_session_articles)


# ═════════════════════════════════════════════════════════
# Tool 1: 네이버 뉴스 웹검색
# ═════════════════════════════════════════════════════════
NAVER_NEWS_ENDPOINT = "https://openapi.naver.com/v1/search/news.json"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def search_web_news(query: str, display: int = 5) -> str:
    """네이버 뉴스 API로 최신 뉴스 검색. 결과를 세션 컨테이너에 저장 + LLM용 텍스트 반환."""
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        return "[에러] .env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 없습니다."

    try:
        response = requests.get(
            NAVER_NEWS_ENDPOINT,
            headers={
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
            },
            params={
                "query": query,
                "display": max(1, min(display, 10)),
                "sort": "date",
            },
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
    except Exception as e:
        return f"[에러] 네이버 뉴스 검색 실패: {e}"

    if not items:
        return f"'{query}' 관련 최신 뉴스를 찾지 못했습니다."

    # UI 표시용 article dict로 변환 → 세션 컨테이너에 누적
    for item in items:
        title = _strip_html(item.get("title", ""))
        desc = _strip_html(item.get("description", ""))
        pub_date = item.get("pubDate", "")[:16]
        link = item.get("originallink") or item.get("link", "")
        _session_articles.append({
            "title": title,
            "content": desc,
            "source": "네이버 뉴스 (웹검색)",
            "published_at": pub_date,
            "url": link,
            "ticker": "",
            "corp_name": "",
            "score": 0.0,
            "faiss_id": -1,
            "from_tool": True,  # UI에서 구분하고 싶다면 이 플래그 사용
        })

    # LLM에 전달할 텍스트
    lines = [f"━ '{query}' 최신 뉴스 {len(items)}건 (네이버, 최신순) ━"]
    for i, item in enumerate(items, 1):
        title = _strip_html(item.get("title", ""))
        desc = _strip_html(item.get("description", ""))
        pub_date = item.get("pubDate", "")[:16]
        link = item.get("originallink") or item.get("link", "")
        lines.append(
            f"[{i}] {title}\n"
            f"    {pub_date} | {link}\n"
            f"    {desc}"
        )
    return "\n\n".join(lines)


# ═════════════════════════════════════════════════════════
# Tool 2: 기존 RAG DB 추가 검색
# ═════════════════════════════════════════════════════════
def search_more_articles(query: str, top_k: int = 5) -> str:
    try:
        articles = rag_search(query, source="articles", top_k=max(1, min(top_k, 10)))
    except Exception as e:
        return f"[에러] RAG 검색 실패: {e}"

    if not articles:
        return f"'{query}' 관련 기사를 DB에서 찾지 못했습니다."

    lines = [f"━ DB 추가 검색 '{query}' {len(articles)}건 ━"]
    for i, a in enumerate(articles, 1):
        title = a.get("title", "")
        source = a.get("source", "")
        date = (a.get("published_at") or "")[:10]
        content = (a.get("content") or "")[:300]
        lines.append(
            f"[{i}] {title}\n"
            f"    {source} | {date}\n"
            f"    {content}"
        )
    return "\n\n".join(lines)


# ═════════════════════════════════════════════════════════
# OpenAI tool 스키마
# ═════════════════════════════════════════════════════════
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_web_news",
            "description": (
                "DB에 저장되지 않은 최신 뉴스를 웹에서 검색합니다 (네이버 뉴스). "
                "최근 며칠 내 발표·이슈를 확인하고 싶을 때 사용하세요. "
                "예: '삼성전자 HBM3E 양산', '현대차 미국 관세 영향'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드. 종목명 + 최근 이슈 키워드 조합 권장",
                    },
                    "display": {
                        "type": "integer",
                        "description": "검색 결과 개수 (1-10, 기본 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_more_articles",
            "description": (
                "기존 DB(FAISS 인덱스)에서 다른 키워드로 기사를 추가 검색합니다. "
                "주제와 관련된 다른 측면(경쟁사 동향, 업종 이슈 등)을 보고 싶을 때 사용하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "FAISS 임베딩 검색에 사용할 자연어 쿼리",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 기사 수 (1-10, 기본 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


TOOL_FUNCTIONS = {
    "search_web_news": search_web_news,
    "search_more_articles": search_more_articles,
}
