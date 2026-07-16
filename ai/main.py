"""
실행: uvicorn main:app --reload --port 8001
"""

from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator import run_debate

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


# ── 토론 생성 (지휘자에게 위임) ──────────────────────────────────────
@app.post("/debate")
def debate(request: DebateRequest):
    return run_debate(request.topic)
