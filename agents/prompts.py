"""
agents/prompts.py — 프롬프트 텍스트 전용 모듈

이 파일에는 LLM에 전달할 프롬프트 문자열을 생성하는 함수만 둡니다.
로직(에이전트 호출, 흐름 제어 등)은 여기 두지 않습니다.

프롬프트를 튜닝/실험할 때는 이 파일만 수정하면 됩니다.
"""

from agents.config import ROLE_META


# ═════════════════════════════════════════════════════════
# System Prompts — 에이전트의 정체성 정의
# ═════════════════════════════════════════════════════════

SYSTEM_PROMPT_BULL = """당신은 주식 투자 강세론자(Bull Analyst)입니다.
해당 종목에 대한 매수/긍정 입장의 논거를 제시하는 역할입니다.

[규칙]
- 반드시 제공된 데이터(기사/정량)에 근거해 주장하세요. 근거 없는 주장은 금지입니다.
- 데이터와 팩트 중심으로 논리적으로 서술하세요.
- 과도한 낙관론은 피하고, 합리적 근거에 집중하세요.
- 응답은 반드시 JSON 형식으로 반환하세요."""

SYSTEM_PROMPT_BEAR = """당신은 주식 투자 약세론자(Bear Analyst)입니다.
해당 종목에 대한 매도/관망/부정 입장의 논거를 제시하는 역할입니다.

[규칙]
- 반드시 제공된 데이터(기사/정량)에 근거해 주장하세요. 근거 없는 주장은 금지입니다.
- 리스크, 불확실성, 부정적 요인을 데이터 기반으로 서술하세요.
- 과도한 비관론은 피하고, 합리적 리스크 분석에 집중하세요.
- 응답은 반드시 JSON 형식으로 반환하세요."""

SYSTEM_PROMPT_MODERATOR = """당신은 주식 투자 토론의 중립적인 사회자(Moderator)입니다.
Bull과 Bear의 토론 내용을 종합하여 균형 잡힌 최종 의견을 제시하는 역할입니다.

[규칙]
- 어느 한쪽 편을 들지 말고 양측 논거를 공정하게 평가하세요.
- Bull의 핵심 근거 요약, Bear의 핵심 리스크 요약을 모두 포함하세요.
- 최종 판단(매수 적극 / 분할 매수 / 관망 / 매도 고려)을 명확히 제시하세요.
- 투자는 본인 책임임을 언급하세요.
- 응답은 반드시 JSON 형식으로 반환하세요."""


# 역할(role) → system prompt 매핑
SYSTEM_PROMPTS = {
    "bull":      SYSTEM_PROMPT_BULL,
    "bear":      SYSTEM_PROMPT_BEAR,
    "moderator": SYSTEM_PROMPT_MODERATOR,
}


# ═════════════════════════════════════════════════════════
# 공용 포맷터 (내부 사용)
# ═════════════════════════════════════════════════════════

def _fmt_articles(articles: list[dict]) -> str:
    if not articles:
        return "  (관련 기사 없음)"
    lines = []
    for i, a in enumerate(articles, 1):
        content_preview = (a.get("content") or a.get("summary") or "")[:500]
        lines.append(
            f"  [{i}] {a.get('title', '')}\n"
            f"      출처: {a.get('source', '')} | {a.get('published_at', '')[:10]}\n"
            f"      내용: {content_preview}"
        )
    return "\n\n".join(lines)


def _articles_block(role: str, articles_common: list[dict], articles_side: list[dict]) -> str:
    display = ROLE_META[role]["display"]
    return (
        "━━━ 공통 참고 기사 ━━━\n"
        f"{_fmt_articles(articles_common)}\n\n"
        f"━━━ {display} 관점 추가 기사 ━━━\n"
        f"{_fmt_articles(articles_side)}"
    )


def _quant_block(quant_text: str) -> str:
    return f"━━━ 정량 데이터 (재무/컨센서스/주가) ━━━\n{quant_text}" if quant_text else ""


def _data_section(
    role: str,
    articles_common: list[dict],
    articles_side: list[dict],
    quant_text: str,
) -> str:
    blocks = []
    if articles_common or articles_side:
        blocks.append(_articles_block(role, articles_common, articles_side))
    if quant_text:
        blocks.append(_quant_block(quant_text))
    return "\n\n".join(blocks) if blocks else "(데이터 없음)"


def _scope_text(round_num: int) -> str:
    if round_num == 1:
        return "정성적 데이터(뉴스 기사)만"
    elif round_num == 2:
        return "정량 데이터(재무/컨센서스/주가)만"
    else:
        return "정성 + 정량 데이터 모두"


# ═════════════════════════════════════════════════════════
# 1. argue 프롬프트 — 독립 주장
# ═════════════════════════════════════════════════════════
def build_argue_prompt(
    role: str,
    topic: str,
    round_num: int,
    articles_common: list[dict],
    articles_side: list[dict],
    quant_text: str = "",
) -> str:
    display = ROLE_META[role]["display"]
    stance  = ROLE_META[role]["stance"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round {round_num}
[당신의 역할]: {display} — {stance} 입장

{_data_section(role, articles_common, articles_side, quant_text)}

━━━ 지시 ━━━
이번 라운드는 {_scope_text(round_num)}을 근거로 합니다.
당신의 {stance} 입장에서 핵심 주장을 제시하세요.
- 반드시 위 데이터에 근거하여 주장하세요.
- 3~5문장으로 간결하게.
- 상대방을 의식하지 말고 자기 입장만 명확히 주장하세요.

반드시 JSON 형식으로 응답하세요:
{{"content": "주장 내용", "tags": ["근거 키워드 1", "근거 키워드 2", "근거 키워드 3"]}}"""


# ═════════════════════════════════════════════════════════
# 2. rebut 프롬프트 — 상대 주장 반박
# ═════════════════════════════════════════════════════════
def build_rebut_prompt(
    role: str,
    topic: str,
    round_num: int,
    opponent_statement: str,
    articles_common: list[dict],
    articles_side: list[dict],
    quant_text: str = "",
) -> str:
    display       = ROLE_META[role]["display"]
    stance        = ROLE_META[role]["stance"]
    opponent_role = "bear" if role == "bull" else "bull"
    opponent_disp = ROLE_META[opponent_role]["display"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round {round_num}
[당신의 역할]: {display} — {stance} 입장

━━━ 반박해야 할 상대({opponent_disp})의 주장 ━━━
{opponent_statement}

{_data_section(role, articles_common, articles_side, quant_text)}

━━━ 지시 ━━━
이번 라운드는 {_scope_text(round_num)}을 근거로 합니다.
위 {opponent_disp}의 주장에 대해 {display}({stance}) 입장에서 반박하세요.
- 반드시 상대 주장의 구체적 논점을 짚어 반박하세요.
- 반박 근거는 위 데이터에서만 가져오세요.
- 3~5문장으로 간결하게.

반드시 JSON 형식으로 응답하세요:
{{"content": "반론 내용", "tags": ["반박 포인트 1", "반박 포인트 2", "반박 포인트 3"]}}"""


# ═════════════════════════════════════════════════════════
# 3. conclude 프롬프트 — 최종 결론 (Round 3)
# ═════════════════════════════════════════════════════════
def build_conclude_prompt(
    role: str,
    topic: str,
    articles_common: list[dict],
    articles_side: list[dict],
    quant_text: str,
) -> str:
    display = ROLE_META[role]["display"]
    stance  = ROLE_META[role]["stance"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round 3 (최종)
[당신의 역할]: {display} — {stance} 입장

{_articles_block(role, articles_common, articles_side)}

{_quant_block(quant_text)}

━━━ 지시 ━━━
이것은 마지막 라운드입니다.
정성 데이터(뉴스)와 정량 데이터(재무/컨센서스/주가) 모두를 종합하여 {display}({stance}) 입장의 **최종 결론**을 제시하세요.
- 핵심 논거를 압축적으로 정리하세요.
- 데이터 근거를 명확히 드러내세요.
- 4~6문장으로 결론을 명확하게.

반드시 JSON 형식으로 응답하세요:
{{"content": "최종 결론", "tags": ["핵심 근거 1", "핵심 근거 2", "핵심 근거 3"]}}"""


# ═════════════════════════════════════════════════════════
# 4. moderator 프롬프트 — 사회자 요약
# ═════════════════════════════════════════════════════════
def build_moderator_prompt(
    topic: str,
    debate_history: list[dict],
    articles_common: list[dict],
) -> str:
    history_text = "\n\n".join(
        f"[Round {h['round']} - {h['role']}]\n{h['content']}"
        for h in debate_history
    )
    articles_text = "\n".join(
        f"- {a.get('title', '')} ({a.get('source', '')})"
        for a in articles_common
    )

    return f"""[토론 주제]: {topic}

━━━ 참고 기사 목록 ━━━
{articles_text}

━━━ 전체 토론 내용 ━━━
{history_text}

위 토론을 종합하여 최종 결론을 JSON 형식으로 제시하세요.
투자 판단(verdict)은 반드시 다음 중 하나로 명시하세요:
매수 적극 | 분할 매수 | 관망 | 매도 고려

응답 형식:
{{
  "bull_summary": "Bull 측 핵심 논거 요약 (2~3문장)",
  "bear_summary": "Bear 측 핵심 리스크 요약 (2~3문장)",
  "conclusion":   "최종 종합 의견 (3~4문장)",
  "verdict":      "매수 적극 | 분할 매수 | 관망 | 매도 고려"
}}"""
