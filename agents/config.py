"""
agents/config.py — 토론 설정 (사용자 편집용)

여기를 수정하면 토론의 모델/온도/발언 순서가 즉시 반영됩니다.
로직 파일(orchestrator, analyst, prompts)은 건드릴 필요 없습니다.
"""

import os


# ─────────────────────────────────────────────────────────
# 1. LLM 모델 설정
# ─────────────────────────────────────────────────────────
MODEL_NAME = "gpt-4o-mini"
# 후보: "gpt-4o", "gpt-4o-mini", "o3-mini", "o1-mini"

REASONING_EFFORT = "medium"  # o1/o3 계열 전용: "low" | "medium" | "high"

# 발언 종류별 temperature (높을수록 다양/창의적, 낮을수록 일관/결정적)
TEMPERATURE = {
    "argue":       0.4,
    "rebut":       0.4,
    "conclude":    0.3,   # 최종 결론은 일관성 중시
    "moderator":   0.3,
    "reflect":     0.1,   # Self-Reflection은 결정적 판단
    "convergence": 0.1,   # 수렴 판정은 결정적 판단
    "profiler":    0.3,   # 설문→독자 프로필 생성
}

# ─────────────────────────────────────────────────────────
# 프롬프트 전략 플래그 (ablation 실험용 on/off)
# ─────────────────────────────────────────────────────────
ENABLE_REFLECTION = True   # Self-Reflection 자기 검토
ENABLE_MEMORY     = False  # 과거 토론 참조
ENABLE_COT        = False  # Chain-of-Thought 단계적 추론
ENABLE_FEW_SHOT   = True   # Few-shot 예시 주입
# RAG는 오케스트레이터의 기본 동작 — 별도 플래그 없음

# ── Agentic 기능 (기본 ON, ablation 시 끄려면 False) ──────
ENABLE_TOOL_CALLING   = True   # 에이전트가 직접 검색/정량 도구 호출 (function calling)
ENABLE_DYNAMIC_ROUNDS = True   # 수렴 판정 기반 동적 라운드 (조기 종료 / 연장)
MAX_DEBATE_ROUNDS     = 3      # 동적 모드: 정성·정량 이후 자유 토론 라운드 최대 횟수

# 조사 방식 (ENABLE_TOOL_CALLING=True일 때만 의미 있음)
#   "per_step": 각 argue/rebut 직전에 매번 (필수) 조사 → 발언. 근거 두툼, 비용 높음.
#   "upfront":  토론 전 각 측이 1회 통합 조사 → 발언 중 도구 미사용. 비용 최저, 근거 얕음.
#   "hybrid":   upfront로 근거를 깔아두고, 발언 중 부족할 때만 (선택) 추가 조사. (기본값)
# 실험 시 env RESEARCH_MODE로 덮어쓸 수 있음 (예: RESEARCH_MODE=per_step python ...)
RESEARCH_MODE = os.getenv("RESEARCH_MODE", "hybrid")

# Tool calling 품질/비용 제어
TOOL_MAX_ROUNDS_PER_STEP = 2    # 한 발언(argue/rebut) 안에서 tool-call 왕복 최대 횟수
TOOL_MAX_CALLS_PER_STEP  = 4    # 한 발언 안에서 실제 실행할 tool call 최대 수
TOOL_SEARCH_TOP_K_DEFAULT = 3   # 모델이 top_k를 생략했을 때 검색 기사 수
TOOL_SEARCH_TOP_K_MAX     = 3   # 모델이 더 크게 요청해도 이 값으로 제한
TOOL_SEARCH_MIN_SCORE     = 0.50  # 이 유사도 미만 검색 결과는 근거/사이드바에서 제외
TOOL_MAX_ARTICLES_PER_SIDE = 12  # 사이드바/result에 보관할 Bull/Bear별 조사 기사 최대 수

PERSONA_STRENGTH  = "standard"  # "mild" | "standard" | "extreme" — 에이전트 페르소나 강도

# ─────────────────────────────────────────────────────────
# 5. 메모리 설정
# ─────────────────────────────────────────────────────────
MEMORY_DIR      = "memory"
MAX_MEMORY_REFS = 2   # 과거 토론 최대 참조 개수

# OpenAI rate limit 발생 시 재시도 횟수와 대기 시간(초)
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = [15, 30]   # 1번째 실패 후 15초, 2번째 실패 후 30초


# ─────────────────────────────────────────────────────────
# 2. RAG 검색 설정
# ─────────────────────────────────────────────────────────
TOP_K_COMMON = 3   # 공통 기사 수
TOP_K_SIDE   = 2   # Bull/Bear 측 기사 수
RAG_MIN_SCORE = 0.35  # 이 유사도 미만 기사는 근거에서 제외(전부 미달이면 안전하게 top_k 유지)


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


# 동적 모드(ENABLE_DYNAMIC_ROUNDS)에서 정성·정량 라운드 이후 반복되는 자유 토론 라운드.
# 수렴 판정이 '미수렴'이면 MAX_DEBATE_ROUNDS 한도까지 이 라운드를 추가 실행합니다.
FREE_DEBATE_ROUND = {
    "name": "자유 토론",
    "data": ["articles", "quant"],
    "steps": [
        {"role": "bull", "action": "argue"},
        {"role": "bear", "action": "rebut", "rebuts": ("bull", "argue")},
        {"role": "bear", "action": "argue"},
        {"role": "bull", "action": "rebut", "rebuts": ("bear", "argue")},
    ],
}


# ─────────────────────────────────────────────────────────
# 4. 역할 메타 (편집할 일은 거의 없지만 표시 텍스트 변경 가능)
# ─────────────────────────────────────────────────────────
ROLE_META = {
    "bull": {"display": "Bull", "stance": "매수(긍정)"},
    "bear": {"display": "Bear", "stance": "매도/관망(부정)"},
}
