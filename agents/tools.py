"""
agents/tools.py — 에이전트가 직접 호출하는 도구(function calling) 정의

ENABLE_TOOL_CALLING이 켜져 있을 때, Bull/Bear 에이전트는 제공된 데이터가
부족하면 아래 도구를 스스로 호출해 추가 정보를 수집합니다.

기존 RAG/정량 함수를 그대로 감싸기만 합니다 (로직 중복 없음).
  - search_articles → rag.retriever.search
  - fetch_quant     → rag.quant_fetcher.fetch_quant
"""

from rag.quant_fetcher import fetch_quant, format_quant
from rag.retriever import search, _detect_ticker
from agents.config import (
    TOOL_SEARCH_MIN_SCORE,
    TOOL_SEARCH_TOP_K_DEFAULT,
    TOOL_SEARCH_TOP_K_MAX,
)


# OpenAI tools 스키마 (chat.completions의 tools 인자에 그대로 전달)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": "종목/주제 관련 뉴스·기사를 의미 기반(임베딩)으로 검색한다. "
                           "제공된 데이터에 없는 근거가 필요할 때 사용한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 쿼리 (자연어). 예: '삼성전자 HBM 공급 계약'",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "가져올 기사 수. 시스템 설정의 상한을 넘으면 자동 제한된다.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_quant",
            "description": "종목의 재무·컨센서스·주가 정량 데이터를 조회한다. "
                           "ticker(6자리 코드) 또는 회사명을 받는다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "6자리 종목 코드(예: 005930) 또는 회사명(예: 삼성전자)",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
]


def tools_for_round(round_num: int) -> list:
    """R1(정성 라운드)에서는 정량 도구(fetch_quant)를 노출하지 않아 정성 근거만 조사하게 한다."""
    if round_num == 1:
        return [s for s in TOOL_SCHEMAS if s["function"]["name"] != "fetch_quant"]
    return TOOL_SCHEMAS


def _format_articles(results: list[dict]) -> str:
    if not results:
        return "(검색 결과 없음)"
    lines = []
    for i, a in enumerate(results, 1):
        snippet = (a.get("content") or a.get("summary") or "")[:300]
        lines.append(
            f"[{i}] {a.get('title', '')} "
            f"({a.get('source', '')}, {(a.get('published_at') or '')[:10]})\n"
            f"    {snippet}"
        )
    return "\n".join(lines)


def _bounded_top_k(raw_top_k) -> int:
    try:
        top_k = int(raw_top_k)
    except (TypeError, ValueError):
        top_k = TOOL_SEARCH_TOP_K_DEFAULT
    top_k = max(1, top_k)
    return min(top_k, TOOL_SEARCH_TOP_K_MAX)


def _filter_by_score(results: list[dict]) -> list[dict]:
    return [
        r for r in results
        if float(r.get("score") or 0.0) >= TOOL_SEARCH_MIN_SCORE
    ]


def cache_key(name: str, args: dict) -> str:
    """동일 tool call 판별용 정규화 키."""
    if name == "search_articles":
        query = (args.get("query") or "").strip().lower()
        top_k = _bounded_top_k(args.get("top_k", TOOL_SEARCH_TOP_K_DEFAULT))
        return f"search_articles:{query}:{top_k}"

    if name == "fetch_quant":
        raw = (args.get("ticker") or "").strip()
        ticker = raw if (len(raw) == 6 and raw.isdigit()) else (_detect_ticker(raw) or raw)
        return f"fetch_quant:{ticker}"

    return f"{name}:{args}"


def dispatch(name: str, args: dict) -> dict:
    """tool_call 실행 → {'text': 모델에 줄 텍스트, 'articles': 검색된 기사 dict 리스트}.

    articles는 search_articles일 때만 채워지며, 사이드바 표시/캡처에 쓰인다.
    """
    if name == "search_articles":
        query = (args.get("query") or "").strip()
        if not query:
            return {"text": "(검색 쿼리 없음)", "articles": []}
        top_k = _bounded_top_k(args.get("top_k", TOOL_SEARCH_TOP_K_DEFAULT))
        results = search(
            query,
            source="articles",
            top_k=top_k,
        )
        results = _filter_by_score(results)
        return {"text": _format_articles(results), "articles": results}

    if name == "fetch_quant":
        raw = (args.get("ticker") or "").strip()
        ticker = raw if (len(raw) == 6 and raw.isdigit()) else (_detect_ticker(raw) or raw)
        data = fetch_quant(ticker)
        text = format_quant(data) if data else f"(정량 데이터 없음: {raw})"
        return {"text": text, "articles": []}

    return {"text": f"(알 수 없는 도구: {name})", "articles": []}
