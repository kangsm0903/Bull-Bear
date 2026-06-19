"""
agents/config.py — 토론 설정 (사용자 편집용)

여기를 수정하면 토론의 모델/온도/발언 순서가 즉시 반영됩니다.
로직 파일(orchestrator, analyst, prompts)은 건드릴 필요 없습니다.
"""


# ─────────────────────────────────────────────────────────
# 1. LLM 모델 설정
# ─────────────────────────────────────────────────────────
MODEL_NAME = "gpt-5.4"
# 후보: "gpt-5.4", "gpt-5", "gpt-5-mini" 등. 정확한 API id는 OpenAI 문서 확인.

# 추론(reasoning) 강도. 추론 모델일 때만 사용: "minimal" | "low" | "medium" | "high"
# 비추론 모델(gpt-4o 등)을 쓸 거면 None으로 두면 temperature가 대신 적용됩니다.
REASONING_EFFORT = "low"

# 발언 종류별 temperature (높을수록 다양/창의적, 낮을수록 일관/결정적)
# ⚠️ REASONING_EFFORT가 설정되면 추론 모델은 temperature를 무시하므로 이 값은 적용되지 않습니다.
TEMPERATURE = {
    "argue":     0.7,
    "rebut":     0.7,
    "conclude":  0.3,   # 최종 결론은 일관성 중시
    "moderator": 0.3,
}

# OpenAI rate limit 발생 시 재시도 횟수와 대기 시간(초)
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = [10, 20]   # 1번째 실패 후 10초, 2번째 실패 후 20초


# ─────────────────────────────────────────────────────────
# 2. RAG 검색 설정
# ─────────────────────────────────────────────────────────
TOP_K_COMMON = 5   # 공통 기사 수 (없으면 있는 만큼만)
TOP_K_SIDE   = 5   # Bull/Bear 측 기사 수 (감성 필터로 부족하면 적게/비워서 반환)

# 하이브리드 검색: 종목별 최신 기사 N개로 후보 풀을 만든 뒤,
# 그 풀 안에서만 유사도순으로 top_k를 선택합니다 (오래된 기사는 후보에서 제외).
# → 최신성(published_at) + 관련성(유사도)을 동시에 확보.
RECENT_POOL  = 30  # 종목별 최신 후보 풀 크기 (published_at 내림차순)

# 감성(호재/악재) 보정 가중치.
#   최종점수 = 유사도 + SENTIMENT_WEIGHT × bias부호 × 감성점수(-1~1)
#   Bull 검색은 호재 기사를, Bear 검색은 악재 기사를 우대.
#   0이면 감성 무시(순수 유사도). 클수록 감성 분리가 강해지지만 관련도는 약해짐.
#   유사도가 보통 0.3~0.5 범위이므로 0.1~0.2 권장.
SENTIMENT_WEIGHT = 0.15

# 감성 라벨링용 LLM 모델 (collection/sentiment_labeler.py가 사용).
# 기사별 호재/악재 점수를 미리 매겨 DB에 저장하는 1회성 작업이라 저렴한 모델로 충분.
SENTIMENT_MODEL = "gpt-4o-mini"


# ─────────────────────────────────────────────────────────
# 3. 토론 흐름 정의 (DEBATE_FLOW)
# ─────────────────────────────────────────────────────────
# 각 라운드 구조:
#   round: 라운드 번호 (1, 2, 3, ...)
#   name:  화면에 표시할 라운드 이름
#   data:  사용할 데이터 종류 ["articles"], ["quant"], ["articles","quant"]
#   steps: 발언 순서 (위에서 아래로 화면에 출력됨)
#
# step 구조:
#   role:    "bull" 또는 "bear"
#   action:  "argue" | "rebut" | "conclude"
#   rebuts:  ("상대 role", "상대 action")  ← action="rebut"일 때만 필수
#            예) ("bull", "argue") = "Bull의 argue 결과를 입력으로 받아 반박"
#
# 의존성이 없는 step들은 자동으로 병렬 실행됩니다.
# 같은 라운드 내에서 모든 argue는 먼저 병렬 실행되고,
# 그것을 rebut하는 step들이 다음에 병렬 실행됩니다.
# ─────────────────────────────────────────────────────────
DEBATE_FLOW = [
    # ─── Round 1: 정성 분석 (찬성 선) ───
    {
        "round": 1,
        "name":  "정성 분석",
        "data":  ["articles"],
        "steps": [
            {"role": "bull", "action": "argue"},
            {"role": "bear", "action": "rebut", "rebuts": ("bull", "argue")},
            {"role": "bear", "action": "argue"},
            {"role": "bull", "action": "rebut", "rebuts": ("bear", "argue")},
        ],
    },

    # ─── Round 2: 정량 분석 (반대 선) ───
    {
        "round": 2,
        "name":  "정량 분석",
        "data":  ["quant"],
        "steps": [
            {"role": "bear", "action": "argue"},
            {"role": "bull", "action": "rebut", "rebuts": ("bear", "argue")},
            {"role": "bull", "action": "argue"},
            {"role": "bear", "action": "rebut", "rebuts": ("bull", "argue")},
        ],
    },

    # ─── Round 3: 최종 결론 (통합) ───
    {
        "round": 3,
        "name":  "최종 결론",
        "data":  ["articles", "quant"],
        "steps": [
            {"role": "bull", "action": "conclude"},
            {"role": "bear", "action": "conclude"},
        ],
    },
]


# ─────────────────────────────────────────────────────────
# 4. 역할 메타 (편집할 일은 거의 없지만 표시 텍스트 변경 가능)
# ─────────────────────────────────────────────────────────
ROLE_META = {
    "bull": {"display": "Bull", "stance": "매수(긍정)"},
    "bear": {"display": "Bear", "stance": "매도/관망(부정)"},
}
