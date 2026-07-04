"""
FastAPI 서버
실행: uvicorn main:app --reload --port 8000
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.orchestrator import DebateOrchestrator

# 토론 결과를 남길 로그 폴더
DEBATE_LOG_DIR = Path(__file__).parent / "logs" / "debates"


def _save_debate_log(topic: str, response: dict) -> None:
    """토론 결과를 logs/debates/{시각}_{주제}.json 으로 저장. 실패해도 응답엔 영향 없음."""
    try:
        DEBATE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w가-힣]+", "_", topic).strip("_")[:40] or "debate"
        record = {"topic": topic, "created_at": datetime.now().isoformat(), **response}
        path = DEBATE_LOG_DIR / f"{ts}_{safe}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📝 토론 로그 저장: {path}")
    except Exception as e:
        print(f"⚠️  토론 로그 저장 실패(무시): {e}")

# verdict → (bull_score, bear_score) — Moderator가 점수를 안 줄 때의 폴백 매핑
VERDICT_SCORES = {
    "적극 매수": (9.0, 3.0),
    "매수":      (8.0, 4.3),
    "분할 매수": (7.0, 5.2),
    "관망":      (5.5, 5.5),
    "비중 축소": (4.5, 6.8),
    "매도 고려": (3.5, 7.8),
    "적극 매도": (2.5, 9.0),
}


# 점수 차이(bull - bear) → verdict 임계값. 위에서부터 매칭.
#   Bull이 더 설득력 있으면 매수 계열, Bear가 더 강하면 매도 계열로
#   '항상' 일관되게 떨어지도록 코드가 결정 (LLM verdict와 score 모순 방지).
VERDICT_THRESHOLDS = [
    (4.0,  "적극 매수"),
    (2.0,  "매수"),
    (0.5,  "분할 매수"),
    (-0.5, "관망"),
    (-2.0, "비중 축소"),
    (-4.0, "매도 고려"),
]
VERDICT_FLOOR = "적극 매도"   # 위 임계값에 안 걸리면(가장 강한 약세)


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _verdict_from_scores(bull: float, bear: float) -> str:
    """bull/bear 점수 차이로 verdict를 결정 (score-verdict 일관성 보장)."""
    diff = bull - bear
    for threshold, verdict in VERDICT_THRESHOLDS:
        if diff >= threshold:
            return verdict
    return VERDICT_FLOOR


def _resolve_verdict_and_scores(mod: dict) -> tuple[str, float, float]:
    """Moderator가 산출한 점수를 0~10으로 받아 verdict를 점수에서 파생.
    점수가 없으면 LLM verdict + 매핑 폴백."""
    bull = _to_number(mod.get("bull_score"))
    bear = _to_number(mod.get("bear_score"))

    if bull is not None and bear is not None:
        bull = max(0.0, min(10.0, bull))
        bear = max(0.0, min(10.0, bear))
        return _verdict_from_scores(bull, bear), bull, bear

    # 폴백: 점수가 없으면 LLM verdict를 쓰고 매핑으로 점수 산출
    verdict = mod.get("verdict", "관망")
    fb_bull, fb_bear = VERDICT_SCORES.get(verdict, (5.5, 5.5))
    return verdict, fb_bull, fb_bear

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
    survey: dict | None = None


@app.post("/api/debate")
def run_debate(req: DebateRequest):
    orchestrator = DebateOrchestrator()
    result = orchestrator.run(topic=req.topic, survey=req.survey)

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
    verdict, bull_score, bear_score = _resolve_verdict_and_scores(mod)

    response = {
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

    _save_debate_log(req.topic, response)
    return response


# ── React 빌드 서빙 (npm run build 이후) ──────────────────
DIST = Path(__file__).parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
