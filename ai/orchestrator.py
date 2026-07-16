"""
토론 지휘자(orchestrator).
종목코드를 찾고 → Bull → Bear → Moderator 순서로 실행 →
결과를 프론트가 기대하는 DebateResponse 모양으로 조립한다.
"""

from datetime import datetime

from agents import run_bull, run_bear, run_moderator
from news import resolve_ticker

# verdict(판정) → (bull_score, bear_score). 지금은 판정을 점수로 바꾸는 단순 표.
VERDICT_SCORES = {
    "매수 적극": (8.5, 3.0),
    "분할 매수": (7.0, 5.0),
    "관망":      (5.5, 5.5),
    "매도 고려": (3.5, 7.5),
}


def _build_articles(bull_articles: list[dict], bear_articles: list[dict]) -> list[dict]:
    """Bull/Bear가 검색해 온 기사를 합치고(중복 제거), 누가 인용했는지 표시해
    프론트 Article 모양으로 변환한다."""
    bull_ids = {a["id"] for a in bull_articles}
    bear_ids = {a["id"] for a in bear_articles}

    merged: dict[str, dict] = {}
    for a in bull_articles + bear_articles:
        merged[a["id"]] = a   # 같은 id면 덮어써서 자동 중복 제거

    result = []
    for aid, a in merged.items():
        if aid in bull_ids and aid in bear_ids:
            ref = "both"
        elif aid in bull_ids:
            ref = "bull"
        else:
            ref = "bear"
        result.append({
            "id": a["id"],
            "title": a["title"],
            "source": a["source"],
            "date": a["published_at"],   # DB의 published_at → 프론트의 date
            "url": a["url"],
            "referencedBy": ref,
        })
    return result


def run_debate(topic: str) -> dict:
    now = datetime.now().isoformat()
    ticker = resolve_ticker(topic)   # "삼성전자" → "005930" (없으면 None)

    # 토론 순서: bull → bear → moderator (각 에이전트는 tool로 기사도 검색)
    bull_text, bull_articles = run_bull(topic, ticker)
    bear_text, bear_articles = run_bear(topic, ticker)
    moderator = run_moderator(topic, bull_text, bear_text)

    messages = [
        {"id": "m1", "agent": "bull", "kind": "argue", "round": 1,
         "message": bull_text, "timestamp": now},
        {"id": "m2", "agent": "bear", "kind": "argue", "round": 1,
         "message": bear_text, "timestamp": now},
    ]

    bull_score, bear_score = VERDICT_SCORES.get(moderator.get("verdict"), (5.5, 5.5))

    return {
        "messages": messages,
        "articles": _build_articles(bull_articles, bear_articles),
        "bull_score": bull_score,
        "bear_score": bear_score,
        "moderator": moderator,
    }
