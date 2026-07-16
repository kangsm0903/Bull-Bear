"""
토론 지휘자(orchestrator).
Bull → Bear → Moderator 순서로 실행하고, 결과를 프론트가 기대하는
DebateResponse 모양(messages/articles/점수/moderator)으로 조립한다.
"""

from datetime import datetime

from agents import run_bull, run_bear, run_moderator

# verdict(판정) → (bull_score, bear_score). 지금은 판정을 점수로 바꾸는 단순 표시
VERDICT_SCORES = {
    "매수 적극": (8.5, 3.0),
    "분할 매수": (7.0, 5.0),
    "관망":      (5.5, 5.5),
    "매도 고려": (3.5, 7.5),
}


def run_debate(topic: str) -> dict:
    now = datetime.now().isoformat()

    # 토론 순서 bull -> bear -> moderator
    bull_text = run_bull(topic)
    bear_text = run_bear(topic)
    moderator = run_moderator(topic, bull_text, bear_text)

    # ④ 조립: 발언들을 프론트 Message 모양으로
    messages = [
        {"id": "m1", "agent": "bull", "kind": "argue", "round": 1,
         "message": bull_text, "timestamp": now},
        {"id": "m2", "agent": "bear", "kind": "argue", "round": 1,
         "message": bear_text, "timestamp": now},
    ]

    # verdict를 점수로 변환 (표에 없으면 중립 5.5/5.5)
    bull_score, bear_score = VERDICT_SCORES.get(moderator.get("verdict"), (5.5, 5.5))

    return {
        "messages": messages,
        "articles": [],            # 기사는 다음 단계(tool calling)에서 채움
        "bull_score": bull_score,
        "bear_score": bear_score,
        "moderator": moderator,
    }
