"""
FastAPI 서버
실행: uvicorn main:app --reload --port 8000
"""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.orchestrator import DebateOrchestrator

# verdict → (bull_score, bear_score)
VERDICT_SCORES = {
    "매수 적극": (8.5, 4.2),
    "분할 매수": (7.2, 5.8),
    "관망":      (5.5, 5.5),
    "매도 고려": (4.0, 7.8),
}

app = FastAPI()

# 개발 중 React dev server(5173) → FastAPI(8000) CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DebateRequest(BaseModel):
    topic: str


@app.post("/api/debate")
def run_debate(req: DebateRequest):
    orchestrator = DebateOrchestrator()
    result = orchestrator.run(topic=req.topic)

    now = datetime.now().strftime("%I:%M %p")

    # ── 메시지 변환 ────────────────────────────────────────
    # result["rounds"]는 라운드별 flat list. 이미 표시 순서대로 정렬됨.
    messages = []
    for round_messages in result["rounds"]:
        for item in round_messages:
            messages.append({
                "id":        str(uuid.uuid4()),
                "agent":     item["role"],          # 'bull' | 'bear'
                "kind":      item["kind"],          # 'argue' | 'rebut' | 'conclude'
                "round":     item["round"],        # 1 | 2 | 3
                "message":   item["content"],
                "timestamp": now,
            })

    # ── 기사 변환 (중복 제거) ───────────────────────────────
    # 같은 기사가 common/bull/bear에 동시에 잡힐 수 있으므로 faiss_id(없으면 url)로 합침.
    # referencedBy: common 포함 또는 bull+bear 양쪽 → "both", 한쪽만 → 해당 진영.
    seen: dict = {}  # key → {"article": a, "sides": set}
    for side in ("common", "bull", "bear"):
        for a in result["articles"][side]:
            key = a.get("faiss_id") or a.get("url") or a.get("title")
            if key not in seen:
                seen[key] = {"article": a, "sides": set()}
            seen[key]["sides"].add(side)

    articles = []
    for entry in seen.values():
        a = entry["article"]
        sides = entry["sides"]
        if "common" in sides or ("bull" in sides and "bear" in sides):
            ref = "both"
        elif "bull" in sides:
            ref = "bull"
        else:
            ref = "bear"
        articles.append({
            "id":           str(uuid.uuid4()),
            "title":        a.get("title", ""),
            "source":       a.get("source", ""),
            "date":         (a.get("published_at") or "")[:10],
            "url":          a.get("url") or "#",
            "referencedBy": ref,
        })

    # ── 점수 / Moderator ───────────────────────────────────
    mod = result["moderator"]
    verdict = mod.get("verdict", "관망")
    bull_score, bear_score = VERDICT_SCORES.get(verdict, (5.5, 5.5))

    return {
        "messages":   messages,
        "articles":   articles,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "moderator": {
            "bull_summary": mod.get("bull_summary", ""),
            "bear_summary": mod.get("bear_summary", ""),
            "conclusion":   mod.get("conclusion", ""),
            "verdict":      verdict,
        },
    }


# ── React 빌드 서빙 (npm run build 이후) ──────────────────
DIST = Path(__file__).parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
