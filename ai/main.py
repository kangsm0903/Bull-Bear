"""
실행: uvicorn main:app --reload --port 8001
"""

from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="BullBear AI Service")

class Survey(BaseModel):
    depth: str | None = None      # 설명 깊이
    horizon: str | None = None    # 희망 투자 기간


class DebateRequest(BaseModel):
    topic: str
    survey: Survey | None = None


# ── 서버가 살아있는지 확인용 ────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── 토론 생성  ──────────────────────────────────────
@app.post("/debate")
def debate(request: DebateRequest):
    topic = request.topic
    now = datetime.now().isoformat()

    messages = [
        {"id": "m1", "agent": "bull", "kind": "argue", "round": 1,
         "message": f"[파이썬 목업] {topic} — 실적 개선 흐름이 뚜렷해 상승 여력이 충분합니다.",
         "timestamp": now},
        {"id": "m2", "agent": "bear", "kind": "argue", "round": 1,
         "message": f"[파이썬 목업] {topic} — 밸류에이션 부담과 거시 리스크가 과소평가돼 있습니다.",
         "timestamp": now},
        {"id": "m3", "agent": "bull", "kind": "conclude", "round": 2,
         "message": "[파이썬 목업] 결론적으로 중장기 관점의 분할 매수가 유효합니다.",
         "timestamp": now},
        {"id": "m4", "agent": "bear", "kind": "conclude", "round": 2,
         "message": "[파이썬 목업] 결론적으로 현시점 진입은 성급하며 관망을 권합니다.",
         "timestamp": now},
    ]

    articles = [
        {"id": "a1", "title": f"[파이썬 목업] {topic} 2분기 실적 시장 기대치 상회",
         "source": "테스트뉴스", "date": "2026-07-06",
         "url": "https://example.com/1", "referencedBy": "bull"},
        {"id": "a2", "title": "[파이썬 목업] 반도체 업황 둔화 우려 확산",
         "source": "테스트뉴스", "date": "2026-07-05",
         "url": "https://example.com/2", "referencedBy": "bear"},
    ]

    moderator = {
        "bull_summary": "[파이썬 목업] 실적 개선과 수급 유입을 근거로 상승을 주장.",
        "bear_summary": "[파이썬 목업] 밸류에이션 부담과 거시 불확실성을 근거로 하락을 주장.",
        "conclusion": "[파이썬 목업] 양측 근거가 팽팽하므로 추가 확인이 필요한 구간.",
        "verdict": "관망",
        "data_balance": "bull 1건 / bear 1건 — 균형",
    }

    return {
        "messages": messages,
        "articles": articles,
        "bull_score": 6.5,
        "bear_score": 5.5,
        "moderator": moderator,
    }
