"""
agents/prompts.py — 프롬프트 텍스트

┌─────────────────────────────────────────────────────────────┐
│ ✏️  [편집 영역]  : 프롬프트를 바꾸려면 여기만 고치면 됩니다.        │
│ ⚙️  [조립 영역]  : 데이터를 끼워넣는 기계적 코드. 보통 안 건드립니다.│
└─────────────────────────────────────────────────────────────┘
"""

from agents.config import ROLE_META


# ═════════════════════════════════════════════════════════════
# ✏️ [편집 영역 1] 페르소나 (시스템 프롬프트)
# ═════════════════════════════════════════════════════════════
SYSTEM_PROMPTS = {
    "bull": """당신은 주식 투자 강세론자(Bull Analyst)입니다.
해당 종목의 매수/긍정 논거를 제시합니다.
- 반드시 제공된 데이터(기사/정량)에 근거하세요. 근거 없는 주장은 금지입니다.
- 과도한 낙관은 피하고 합리적 근거에 집중하세요.
- 모든 문장은 '~합니다/~습니다' 존댓말로, JSON으로만 응답하세요.
- 400자 이내로 작성하세요.
""",

    "bear": """당신은 주식 투자 약세론자(Bear Analyst)입니다.
해당 종목의 매도/관망/부정 논거를 제시합니다.
- 반드시 제공된 데이터(기사/정량)에 근거하세요. 근거 없는 주장은 금지입니다.
- 과도한 비관은 피하고 합리적 리스크 분석에 집중하세요.
- 모든 문장은 '~합니다/~습니다' 존댓말로, JSON으로만 응답하세요.
- 400자 이내로 작성하세요.
""",

    "moderator": """당신은 주식 투자 토론의 중립적 사회자(Moderator)입니다.
Bull/Bear 논거를 공정하게 평가해 균형 잡힌 최종 의견을 제시합니다.
- 한쪽 편을 들지 말고 양측을 공정히 평가하세요.
- 투자는 본인 책임임을 전제하세요.
- 모든 문장은 '~합니다/~습니다' 존댓말로, JSON으로만 응답하세요.""",
}


# ═════════════════════════════════════════════════════════════
# ✏️ [편집 영역 2] 발언별 출력 필드 (필드명 → 설명)
#   · dict 순서대로 화면에 줄바꿈(\n)으로 표시됩니다.
#   · 설명은 모델에게 "그 필드에 무엇을 담을지" 안내합니다.
# ═════════════════════════════════════════════════════════════
FIELDS = {
    "argue": {
        "assertion":  "주장: 논제에 대한 입장을 한 문장으로",
        "reason":     "이유: 그렇게 보는 근본 배경",
        "evidence":   "근거: 제공된 데이터의 사실·수치·사례 인용",
        "conclusion": "결론: 입장을 다시 강조",
    },
    "rebut": {
        "they_say":  "they_say: 상대 주장의 핵심을 왜곡 없이 요약하고, 그중 타당한 부분이 있으면 솔직히 인정",
        "but":       "but: 동의할 수 없는 '핵심 한 지점'을 분명히 제시 (단, 데이터로 반박이 약하면 억지 반대 대신 부분 동의로 마무리해도 됨)",
        "because":   "because: 위 지적을 데이터의 사실·수치·반박 사례로 증명",
        "therefore": "therefore: 인정할 점과 반박할 점을 종합해 최종 입장을 균형 있게 정리",
    },
    "conclude": {
        "assertion":  "assertion: 최종 입장을 '수준'까지 명시 (단순 매수/관망이 아니라 적극/분할/소극 등)",
        "reason":     "reason: 그 결론에 이른 핵심 논리",
        "evidence":   "evidence: 정성·정량 데이터의 결정적 근거",
        "conclusion": "conclusion: 투자 기간(예: 3~6개월)과 조건·트리거(예: 다음 실적 발표 확인), 주의 포인트를 함께 제시",
    },
}


# ═════════════════════════════════════════════════════════════
# ✏️ [편집 영역 3] 발언별 지시문
#   사용 가능한 치환자: {display} {stance} {scope} {opponent}
# ═════════════════════════════════════════════════════════════
GUIDES = {
    "argue": """당신은 {display}({stance}) 입장입니다. 이번 라운드는 {scope}만 근거로 합니다.
아래 각 항목을 1~2문장의 존댓말로 '간결하게' 작성하세요. 반드시 제공된 데이터에 근거하세요.""",

    "rebut": """당신은 {display}({stance}) 입장입니다. 이번 라운드는 {scope}만 근거로 합니다.
위 {opponent}의 주장에 대해 아래 각 항목을 1~2문장의 존댓말로 '간결하게' 작성하세요.
[태도] 무조건 반대하지 마세요. 상대 논리 중 납득되는 부분은 먼저 인정한 뒤,
반박 포인트가 명확할 때만 데이터로 강하게 반박하세요. 반박 근거가 약하면 부분 동의로 마무리해도 됩니다.""",

    "conclude": """당신은 {display}({stance}) 입장입니다.
정성·정량 데이터를 종합해 최종 결론을 아래 각 항목별로 1~2문장의 존댓말로 '간결하게' 작성하세요.
[판단 구체화] '무조건 매수/관망' 같은 단정 대신, 판단의 수준(적극/분할/소극)과
투자 기간, 확인해야 할 조건·이벤트(예: 다음 실적 발표), 주의 포인트를 함께 제시하세요.""",
}


# ✏️ 사회자 지시문 (출력 구조가 달라 따로 둠)
MODERATOR_GUIDE = """양측 논거를 공정하게 평가해 최종 의견을 제시하세요. 모든 문장은 존댓말로, 간결하게.
- bull_summary: Bull 핵심 논거 요약 (2~3문장)
- bear_summary: Bear 핵심 리스크 요약 (2~3문장)
- conclusion:   최종 종합 의견. 다음을 모두 포함하세요 — ① 판단 수준(적극/분할/소극/관망 정도)
                ② 투자 기간(예: 3~6개월) ③ 확인할 조건·트리거(예: 다음 실적 발표·특정 지표)
                ④ 주의 포인트. '무조건 매수/관망' 같은 단정은 피하세요. (3~4문장)
- verdict:      아래 4개 중 하나만"""

VERDICT_OPTIONS = "매수 적극 | 분할 매수 | 관망 | 매도 고려"


# ═════════════════════════════════════════════════════════════
# ⚙️ [조립 영역] — 보통 안 건드려도 됩니다
# ═════════════════════════════════════════════════════════════

# orchestrator가 content를 \n으로 합칠 때 쓰는 필드 순서 (FIELDS에서 자동 도출)
CONTENT_FIELDS = {action: list(spec) for action, spec in FIELDS.items()}

# 라운드 → 데이터 범위 텍스트
SCOPE = {1: "정성 데이터(뉴스 기사)", 2: "정량 데이터(재무/컨센서스/주가)", 3: "정성+정량 데이터"}


def _fmt_articles(articles: list[dict]) -> str:
    if not articles:
        return "  (관련 기사 없음)"
    return "\n\n".join(
        f"  [{i}] {a.get('title','')}\n"
        f"      출처: {a.get('source','')} | {a.get('published_at','')[:10]}\n"
        f"      내용: {(a.get('content') or '')[:500]}"
        for i, a in enumerate(articles, 1)
    )


def _context(role: str, articles_common: list[dict], articles_side: list[dict], quant_text: str) -> str:
    """기사 + 정량 데이터 블록을 하나로 조립."""
    blocks = []
    if articles_common or articles_side:
        disp = ROLE_META[role]["display"]
        blocks.append(
            f"━━━ 공통 참고 기사 ━━━\n{_fmt_articles(articles_common)}\n\n"
            f"━━━ {disp} 관점 추가 기사 ━━━\n{_fmt_articles(articles_side)}"
        )
    if quant_text:
        blocks.append(f"━━━ 정량 데이터 ━━━\n{quant_text}")
    return "\n\n".join(blocks) if blocks else "(데이터 없음)"


def _field_lines(action: str) -> str:
    return "\n".join(f"  · {desc}" for desc in FIELDS[action].values())


def _schema(action: str) -> str:
    body = ", ".join(f'"{f}": "..."' for f in CONTENT_FIELDS[action])
    return "{" + body + ', "tags": ["키워드1", "키워드2", "키워드3"]}'


# ── 빌더 ─────────────────────────────────────────────────────
def build_argue_prompt(role, topic, round_num, articles_common, articles_side, quant_text=""):
    guide = GUIDES["argue"].format(
        display=ROLE_META[role]["display"],
        stance=ROLE_META[role]["stance"],
        scope=SCOPE[round_num],
    )
    return f"""[토론 주제] {topic}  ·  Round {round_num}

{_context(role, articles_common, articles_side, quant_text)}

━━━ 지시 ━━━
{guide}
{_field_lines("argue")}

JSON으로만 응답:
{_schema("argue")}"""


def build_rebut_prompt(role, topic, round_num, opponent_statement,
                       articles_common, articles_side, quant_text=""):
    opponent = ROLE_META["bear" if role == "bull" else "bull"]["display"]
    guide = GUIDES["rebut"].format(
        display=ROLE_META[role]["display"],
        stance=ROLE_META[role]["stance"],
        scope=SCOPE[round_num],
        opponent=opponent,
    )
    return f"""[토론 주제] {topic}  ·  Round {round_num}

━━━ 반박 대상: {opponent}의 주장 ━━━
{opponent_statement}

{_context(role, articles_common, articles_side, quant_text)}

━━━ 지시 ━━━
{guide}
{_field_lines("rebut")}

JSON으로만 응답:
{_schema("rebut")}"""


def build_conclude_prompt(role, topic, articles_common, articles_side, quant_text):
    guide = GUIDES["conclude"].format(
        display=ROLE_META[role]["display"],
        stance=ROLE_META[role]["stance"],
    )
    return f"""[토론 주제] {topic}  ·  Round 3 (최종)

{_context(role, articles_common, articles_side, quant_text)}

━━━ 지시 ━━━
{guide}
{_field_lines("conclude")}

JSON으로만 응답:
{_schema("conclude")}"""


def build_moderator_prompt(topic, debate_history, articles_common):
    history_text = "\n\n".join(
        f"[Round {h['round']} - {h['role']}]\n{h['content']}" for h in debate_history
    )
    articles_text = "\n".join(
        f"- {a.get('title','')} ({a.get('source','')})" for a in articles_common
    )
    return f"""[토론 주제] {topic}

━━━ 참고 기사 ━━━
{articles_text}

━━━ 전체 토론 ━━━
{history_text}

━━━ 지시 ━━━
{MODERATOR_GUIDE}
verdict 선택지: {VERDICT_OPTIONS}

JSON으로만 응답:
{{"bull_summary": "...", "bear_summary": "...", "conclusion": "...", "verdict": "<{VERDICT_OPTIONS}>"}}"""
