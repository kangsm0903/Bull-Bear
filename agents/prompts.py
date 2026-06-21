"""
agents/prompts.py — 프롬프트 텍스트 전용 모듈

이 파일에는 LLM에 전달할 프롬프트 문자열을 생성하는 함수만 둡니다.
로직(에이전트 호출, 흐름 제어 등)은 여기 두지 않습니다.

프롬프트를 튜닝/실험할 때는 이 파일만 수정하면 됩니다.
"""

from agents.config import (
    ROLE_META,
    ENABLE_COT,
    ENABLE_FEW_SHOT,
    ENABLE_TOOL_CALLING,
    PERSONA_STRENGTH,
    RESEARCH_MODE,
)


# ═════════════════════════════════════════════════════════
# 유저 페르소나 프로필
# ═════════════════════════════════════════════════════════

PERSONA_PROFILES = {
    "입문자": (
        "이 토론의 독자는 주식 투자 경험이 거의 없는 입문자입니다.\n"
        "- 전문 용어는 괄호 안에 간단히 설명하세요 (예: PER(주가수익비율))\n"
        "- 결론을 첫 문장에 명확히 제시하고, 이유 2가지로 설명하세요\n"
        "- 비유나 일상적 표현을 활용해 이해하기 쉽게 서술하세요"
    ),
    "개인투자자": (
        "이 토론의 독자는 주식 투자 경험이 있는 개인 투자자입니다.\n"
        "- 핵심 수치(PER, 영업이익, 주가 등)를 직접 인용하세요\n"
        "- 투자 판단에 필요한 시사점을 명확히 제시하세요\n"
        "- 표준 금융 용어를 사용하되, 논리적 흐름을 따라가기 쉽게 서술하세요"
    ),
    "전문가": (
        "이 토론의 독자는 기관 투자자 수준의 전문 투자자입니다.\n"
        "- 재무 수치(ROE, EV/EBITDA, 마진율 등)와 밸류에이션을 정밀하게 분석하세요\n"
        "- 리스크를 구체적으로 수치화하고 시나리오별로 언급하세요\n"
        "- 간결하고 밀도 높은 분석 언어를 사용하세요"
    ),
}


def _cot_block_argue(role: str, stance: str) -> str:
    if not ENABLE_COT:
        return ""
    return f"""
━━━ 추론 단계 (Chain-of-Thought) ━━━
최종 주장을 쓰기 전에 아래 순서로 추론하세요:
1. [데이터 추출] 제공된 데이터에서 인용 가능한 수치·사실을 3개 이상 나열하세요
2. [근거 선택] {stance} 입장을 가장 강하게 뒷받침하는 근거 2~3개를 고르세요
3. [논리 연결] 각 근거의 원인→결과 관계를 한 줄로 정리하세요
4. [주장 구성] 위 추론을 바탕으로 4~6문장의 최종 주장을 작성하세요
"""


def _cot_block_rebut(opponent_disp: str, stance: str) -> str:
    if not ENABLE_COT:
        return ""
    return f"""
━━━ 추론 단계 (Chain-of-Thought) ━━━
반박을 쓰기 전에 아래 순서로 추론하세요:
1. [논점 파악] {opponent_disp}의 주장에서 핵심 논점 2~3개를 추출하세요
2. [약점 탐색] 각 논점의 논리적 약점 또는 데이터 불일치를 찾으세요
3. [반박 근거] 제공된 데이터에서 각 약점을 반박할 수치·사실을 찾으세요
4. [반박 구성] 상대 논점을 직접 겨냥한 3~5문장의 반박을 작성하세요
"""


def _output_format_argue() -> str:
    if ENABLE_COT:
        return (
            '{"reasoning": "추론 1~3단계 요약", '
            '"content": "최종 주장 (4~6문장)", '
            '"tags": ["근거 키워드1", "근거 키워드2", "근거 키워드3"]}'
        )
    return '{"content": "주장 내용", "tags": ["근거 키워드 1", "근거 키워드 2", "근거 키워드 3"]}'


def _output_format_rebut() -> str:
    if ENABLE_COT:
        return (
            '{"reasoning": "추론 1~3단계 요약", '
            '"content": "반론 내용 (3~5문장)", '
            '"tags": ["반박 포인트1", "반박 포인트2", "반박 포인트3"]}'
        )
    return '{"content": "반론 내용", "tags": ["반박 포인트 1", "반박 포인트 2", "반박 포인트 3"]}'


_FEW_SHOT_NOTICE = (
    "※ 위 예시의 [수치]·[지표] 표기는 구조 설명용 자리표시자입니다. "
    "실제 논거는 반드시 위에 제공된 데이터에서만 인용하세요."
)

_FEW_SHOT_ARGUE = {
    "bull": f"""\
━━━ 출력 예시 (좋은 매수 주장 — 구조 참고용) ━━━
[가정] 데이터에 [목표주가 상향], [영업이익 전망 상향], [시장점유율 확대] 정보가 있는 경우
{{
  "reasoning": "1. [데이터 추출] [목표주가 N만원 상향] / [영업이익 X% 상향] / [점유율 A→B%]. 2. [근거 선택] 이익 모멘텀([X]% 상향)과 경쟁우위(점유율 확대)가 핵심. 3. [논리 연결] 점유율 확대→매출 증가→이익 개선→목표주가 상향의 선순환.",
  "content": "영업이익 전망치가 [X]% 상향 조정되어 이익 모멘텀이 뚜렷합니다. 시장점유율이 [A]%에서 [B]%로 확대된 점은 경쟁우위 강화를 실증하며 매출 성장의 지속가능성을 뒷받침합니다. 이를 반영해 목표주가가 [N]만원으로 상향되었으며, 현재 주가는 추가 상승 여력이 존재합니다.",
  "tags": ["이익 모멘텀", "점유율 확대", "목표주가 상향"]
}}
{_FEW_SHOT_NOTICE}""",

    "bear": f"""\
━━━ 출력 예시 (좋은 매도 주장 — 구조 참고용) ━━━
[가정] 데이터에 [고PER], [성장률 둔화], [원가 압박] 정보가 있는 경우
{{
  "reasoning": "1. [데이터 추출] [PER X배(섹터 평균 Y배)] / [성장률 A%→B% 둔화] / [원가 압박 요인]. 2. [근거 선택] 밸류에이션 리스크와 성장 둔화가 핵심 약점. 3. [논리 연결] 성장 둔화 지속 시 고PER 정당화 불가→멀티플 축소→주가 하방 압력.",
  "content": "현재 PER [X]배는 섹터 평균 [Y]배 대비 프리미엄 상태로, 성장이 둔화될 경우 이 프리미엄을 유지하기 어렵습니다. 실제로 매출 성장률이 [A]%에서 [B]%로 둔화되고 있으며, 원가 압박 요인까지 더해져 마진 개선 여지가 제한적입니다. 이익 모멘텀 약화와 고밸류에이션이 겹칠 경우 멀티플 축소 위험이 큽니다.",
  "tags": ["밸류에이션 리스크", "성장 둔화", "마진 압박"]
}}
{_FEW_SHOT_NOTICE}""",
}

_FEW_SHOT_REBUT = f"""\
━━━ 출력 예시 (좋은 반박 — 구조 참고용) ━━━
[가정] 상대가 [목표주가 상향]을 저평가 근거로 사용했고, 데이터에 [목표주가 달성률], [현재 밸류에이션] 정보가 있는 경우
{{
  "reasoning": "1. [논점 파악] 상대는 [목표주가 상향]을 저평가 근거로 사용. 2. [약점 탐색] 목표주가는 추정치라 달성률이 낮다는 점이 약점. 3. [반박 근거] 데이터의 [달성률 수치]와 [현재 밸류에이션]으로 반박.",
  "content": "목표주가 상향이 곧 저평가를 의미하지는 않습니다. 데이터에 따르면 목표주가 달성률이 [X]%에 불과해 실현 가능성에 의문이 따릅니다. 더불어 현재 밸류에이션은 섹터 평균을 상회하며, 이미 낙관적 전망이 주가에 반영된 상태임을 시사합니다.",
  "tags": ["목표주가 신뢰성", "밸류에이션 부담", "추정치 한계"]
}}
{_FEW_SHOT_NOTICE}"""


# ── 입문자(beginner) 전용 쉬운 설명 버전 few-shot ──────────
# 전문용어를 괄호로 풀이하고, 첫째/둘째 구조 + 일상어로 서술 (수치는 동일하게 데이터에서만 인용).
_FEW_SHOT_ARGUE_PLAIN = {
    "bull": f"""\
━━━ 출력 예시 (쉬운 설명 버전 — 구조 참고용) ━━━
[가정] 데이터에 [목표주가 상향], [영업이익 전망 상향] 정보가 있는 경우
{{
  "reasoning": "1. 데이터에서 [영업이익 [X]% 상향], [목표주가 [N]만원 상향] 확인. 2. 이익이 늘고 적정주가가 올랐으니 매수 근거. 3. 쉬운 말로 풀어서 전달.",
  "content": "삼성전자는 지금 관심을 가질 만한 이유가 있습니다. 첫째, 회사가 벌 것으로 보이는 이익(영업이익)이 [X]% 늘었습니다. 이익이 늘면 보통 주가에도 긍정적입니다. 둘째, 증권사들이 보는 적정 주가(목표주가)가 [N]만원으로 올랐는데, 이는 지금 주가가 그보다 싸다는 뜻(저평가)입니다. 쉽게 말해 회사는 더 잘 벌고 있는데 주가는 아직 그만큼 따라오지 못한 상황입니다.",
  "tags": ["이익 증가", "목표주가 상향", "저평가"]
}}
{_FEW_SHOT_NOTICE}""",

    "bear": f"""\
━━━ 출력 예시 (쉬운 설명 버전 — 구조 참고용) ━━━
[가정] 데이터에 [고PER], [성장률 둔화] 정보가 있는 경우
{{
  "reasoning": "1. [PER [X]배(섹터 [Y]배)], [성장률 [A]%→[B]% 둔화] 확인. 2. 비싸고 성장 느려짐이 약점. 3. 쉬운 말로 전달.",
  "content": "삼성전자는 지금 조심할 부분도 있습니다. 첫째, 주가가 이익에 비해 비싼 편입니다. 이익 대비 주가 수준을 보는 지표(PER)가 [X]배로, 비슷한 회사 평균 [Y]배보다 높습니다. 둘째, 매출이 느는 속도(성장률)가 [A]%에서 [B]%로 느려지고 있습니다. 쉽게 말해 가격은 비싼데 성장은 식고 있어 지금 사기엔 부담이 있습니다.",
  "tags": ["비싼 주가", "성장 둔화", "부담"]
}}
{_FEW_SHOT_NOTICE}""",
}

_FEW_SHOT_REBUT_PLAIN = f"""\
━━━ 출력 예시 (쉬운 설명 버전 — 구조 참고용) ━━━
[가정] 상대가 [목표주가 상향]을 저평가 근거로 사용한 경우
{{
  "reasoning": "1. 상대는 [목표주가 상향]을 저평가 근거로 사용. 2. 목표주가는 예상치라 실제 도달 못 할 수 있음. 3. 쉬운 말로 반박.",
  "content": "목표주가가 올랐다고 해서 꼭 싼 것은 아닙니다. 목표주가는 증권사의 '예상 가격'일 뿐인데, 데이터를 보면 실제로 그 가격에 도달한 비율(달성률)이 [X]%에 그칩니다. 쉽게 말해 기대만큼 오르지 못한 경우가 많았다는 뜻입니다. 따라서 목표주가가 올랐다는 사실만으로 싸다고 보긴 이릅니다.",
  "tags": ["목표주가는 예상치", "낮은 달성률", "신중"]
}}
{_FEW_SHOT_NOTICE}"""


# 독자 등급 매핑 (few-shot 변형 선택용)
PRESET_TIER = {"입문자": "beginner", "개인투자자": "intermediate", "전문가": "expert"}


def resolve_persona_tier(user_persona: str = "", survey: dict | None = None) -> str:
    """few-shot 변형 선택용 거친 등급. 설문이 있으면 규칙으로, 없으면 프리셋 키로 산출."""
    if survey:
        level = survey.get("level")
        term  = survey.get("terminology")
        depth = survey.get("depth")
        if level == "입문자" or term == "낮음" or depth == "쉽고 간단":
            return "beginner"
        if level == "전문가" or term == "높음":
            return "expert"
        return "intermediate"
    return PRESET_TIER.get(user_persona, "")


def _few_shot_argue(role: str, persona_tier: str = "") -> str:
    if not ENABLE_FEW_SHOT:
        return ""
    examples = _FEW_SHOT_ARGUE_PLAIN if persona_tier == "beginner" else _FEW_SHOT_ARGUE
    return f"\n{examples.get(role, '')}\n"


def _few_shot_rebut(persona_tier: str = "") -> str:
    if not ENABLE_FEW_SHOT:
        return ""
    example = _FEW_SHOT_REBUT_PLAIN if persona_tier == "beginner" else _FEW_SHOT_REBUT
    return f"\n{example}\n"


def _persona_block(user_persona: str) -> str:
    """독자 맞춤 작성 지침 블록 생성 (지시형).

    user_persona가 프리셋 키(입문자/개인투자자/전문가)면 해당 프로필로 확장하고,
    아니면 (설문→LLM으로 생성된) 자유형 프로필 문자열을 그대로 사용한다.
    """
    if not user_persona or not user_persona.strip():
        return ""
    profile = PERSONA_PROFILES.get(user_persona, user_persona).strip()
    return (
        "\n━━━ 독자 맞춤 작성 지침 (필수) ━━━\n"
        "아래 독자 수준에 맞춰 작성하세요. 투자 판단·근거·수치는 그대로 두되, "
        "용어 풀이·설명 깊이·문장 난이도·톤만 이 수준에 맞추세요:\n"
        f"{profile}\n"
    )


def _persona_directive(user_persona: str) -> str:
    """지시부 끝에 붙는 페르소나 적용 리마인더 (페르소나 있을 때만)."""
    if not user_persona or not user_persona.strip():
        return ""
    return (
        "\n- 위 '독자 맞춤 작성 지침'에 맞춰 용어 풀이·설명 깊이·문장 난이도를 조절하세요. "
        "(분석 내용·결론·수치는 독자와 무관하게 동일하게 유지)"
    )


# ── 희망 투자기간 → 근거 강조 (톤이 아닌 '무엇을 부각할지'를 결정) ──
HORIZON_EMPHASIS = {
    "단기": "단기(수개월 이내) 투자자입니다. 같은 분석 안에서 촉매(이벤트)·실적 모멘텀/서프라이즈·수급·투자심리 등 단기 주가에 영향을 주는 근거를 우선 부각하세요.",
    "중기": "중기(6개월~1년) 투자자입니다. 같은 분석 안에서 실적 추세·밸류에이션 정상화·업황 사이클 등 중기 관점 근거를 우선 부각하세요.",
    "장기": "장기(1년 이상) 투자자입니다. 같은 분석 안에서 구조적 경쟁우위(해자)·산업 성장성·재무 건전성·장기 밸류에이션 등 장기 관점 근거를 우선 부각하세요.",
}


def _horizon_directive(horizon: str) -> str:
    """희망 투자기간에 맞춰 '어떤 근거를 부각할지'를 지시. 최종 판단·수치는 불변."""
    emphasis = HORIZON_EMPHASIS.get(horizon, "")
    if not emphasis:
        return ""
    return (
        "\n━━━ 투자기간 관점 (근거 강조) ━━━\n"
        f"독자는 {emphasis}\n"
        "단, 어떤 근거를 부각하든 최종 투자판단·수치·사실은 투자기간과 무관하게 동일하게 유지하세요.\n"
    )


def _tools_block(stance: str, action: str = "argue", round_num: int = 0) -> str:
    """조사 방식에 따라 발언별 도구 사용 지시를 주입.

    - per_step: 모든 발언에서 자료 조사를 '필수'로 지시.
    - hybrid:   사전 조사 근거를 기본 사용하되, rebut에서만 '선택적' 추가 조사 허용.
                (argue는 사전 조사 근거만 사용하므로 블록 없음)
    - upfront/OFF: 발언 중 도구를 쓰지 않으므로 빈 블록.

    R1(정성 라운드)에서는 fetch_quant(정량) 안내를 빼고 search_articles만 권한다.
    (실제 도구 노출 차단은 analyst의 tools_for_round로 결정적으로 처리.)
    """
    if not ENABLE_TOOL_CALLING:
        return ""
    if RESEARCH_MODE == "per_step":
        quant_line = (
            "- 이 라운드는 정성 분석이므로 fetch_quant(정량 데이터)는 사용하지 말고 search_articles만 사용하세요.\n"
            if round_num == 1 else
            "- fetch_quant(ticker): 필요 시 정량 데이터 조회.\n"
        )
        return (
            "\n━━━ 자료 조사 (필수) ━━━\n"
            f"위 공통 브리핑 외의 side 근거는 별도 리서치 단계에서 수집합니다. {stance} 논거를 뒷받침할 자료를 먼저 조사하세요.\n"
            f"- search_articles(query): 본인({stance}) 입장을 강화하거나 검증할 뉴스를 검색하세요.\n"
            f"{quant_line}"
            "최종 발언은 리서치가 끝난 뒤 작성하고, 찾은 근거에서만 인용하세요. "
            "검색 결과가 비거나 근거가 부족하면 수치를 지어내지 말고 '근거 부족'으로 인정하세요.\n"
        )
    if RESEARCH_MODE == "hybrid" and action == "rebut":
        tool_line = (
            "- search_articles(query): 꼭 필요한 경우에만 호출하세요. 이 라운드는 정성 분석이므로 fetch_quant(정량)는 사용하지 마세요.\n"
            if round_num == 1 else
            "- search_articles(query) / fetch_quant(ticker): 꼭 필요한 경우에만 호출하세요.\n"
        )
        return (
            "\n━━━ 자료 조사 (선택) ━━━\n"
            f"위에 이미 사전 조사된 {stance} 측 근거가 제공돼 있습니다. 기본적으로는 이 근거로 반박하세요.\n"
            "다만 상대가 제기한 논점이 사전 근거로 반박되지 않을 때만 추가 조사를 하세요.\n"
            f"{tool_line}"
            "추가 조사가 필요 없으면 도구를 호출하지 말고 바로 반박하세요. 찾은 근거에서만 인용하고, 수치를 지어내지 마세요.\n"
        )
    return ""


# ═════════════════════════════════════════════════════════
# System Prompts — 에이전트의 정체성 정의
# ═════════════════════════════════════════════════════════

_BULL_PROMPTS = {
    "mild": """당신은 온건한 매수 의견을 가진 셀사이드 주식 애널리스트입니다.
데이터가 뒷받침하는 범위 내에서만 매수 논거를 제시하며, 불확실성은 솔직하게 인정합니다.

[분석 방향]
- 매수 근거가 명확할 때만 강하게 주장하고, 불확실한 경우 조건부 의견을 제시하세요.
- 반대 논거의 합리적인 부분은 인정하되, 그럼에도 매수가 적합한 이유를 논리적으로 설명하세요.
- 4가지 축(밸류에이션·이익 모멘텀·성장 동력·경쟁우위) 중 데이터가 실제로 지지하는 축만 사용하세요.

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 모든 수치는 제공된 데이터에 명시된 것만 사용하세요. 추정·가정·생성은 절대 금지입니다.
- 응답은 반드시 JSON 형식으로 반환하세요.""",

    "standard": """당신은 매수 의견 셀사이드 주식 애널리스트입니다.
제공된 데이터를 근거로 다음 4가지 분석 축 중심으로 매수 논거를 구성하세요.

[4가지 분석 축]
① 밸류에이션: 현재 PER/PBR이 역사적 밴드 또는 컨센서스 목표가 대비 저평가 근거
② 이익 모멘텀: 영업이익/순이익 개선 추세, EPS 상향 가능성, 이익률 확대 여부
③ 성장 동력: 매출 성장의 지속가능성, 신규 사업/시장 기회, 수주 잔고
④ 경쟁우위: 시장 지위, 기술적 해자(모트), 섹터 내 포지셔닝

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 주가, 수익률, 재무 수치 등 모든 숫자는 반드시 제공된 데이터에 명시된 것만 사용하세요. 데이터에 없는 수치를 추정·가정·생성하는 것은 절대 금지입니다.
- 4가지 축 중 가장 강한 2~3가지를 중심으로 논거를 구성하세요.
- 과도한 낙관론은 피하고, 데이터에 기반한 합리적 근거에 집중하세요.
- 응답 전에 출력의 모든 수치가 위 데이터에서 확인 가능한지 반드시 검토하세요.
- 응답은 반드시 JSON 형식으로 반환하세요.""",

    "extreme": """당신은 강성 매수 신봉자입니다. 어떤 상황에서도 적극 매수 입장을 견지하며, 약세 논거는 일시적 노이즈로 일축합니다.

[분석 방향]
- 제공된 데이터에서 매수 근거가 될 수 있는 모든 요소를 최대한 강하게 부각하세요.
- 리스크가 언급되더라도 단기적·사소한 것으로 최소화하고, 매수 논거로 재해석하세요.
- 상대의 약세 주장은 근거가 불충분하거나 과장된 것으로 직접적으로 일축하세요.
- 강한 확신과 명확한 매수 주장을 전면에 내세우세요.

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 모든 수치는 제공된 데이터에 명시된 것만 사용하세요. 추정·가정·생성은 절대 금지입니다.
- 응답은 반드시 JSON 형식으로 반환하세요.""",
}

_BEAR_PROMPTS = {
    "mild": """당신은 온건한 매도/중립 의견을 가진 셀사이드 주식 애널리스트입니다.
데이터가 뒷받침하는 범위 내에서만 리스크를 제시하며, 긍정적 신호는 공정하게 인정합니다.

[분석 방향]
- 리스크가 명확할 때만 강하게 경고하고, 불확실한 경우 조건부 우려를 표명하세요.
- 매수 논거의 합리적인 부분은 인정하되, 그럼에도 리스크가 더 중요한 이유를 설명하세요.
- 4가지 리스크 축 중 데이터가 실제로 지지하는 축만 사용하세요.

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 모든 수치는 제공된 데이터에 명시된 것만 사용하세요. 추정·가정·생성은 절대 금지입니다.
- 응답은 반드시 JSON 형식으로 반환하세요.""",

    "standard": """당신은 매도/중립 의견 셀사이드 주식 애널리스트입니다.
제공된 데이터를 근거로 다음 4가지 리스크 축 중심으로 약세 논거를 구성하세요.

[4가지 리스크 축]
① 밸류에이션 리스크: 현재 멀티플이 이익 대비 과도하거나, 이익 감소 시 재평가 위험
② 실적 하향 리스크: 매출 성장 둔화, 마진 압박, 시장 컨센서스 하향 조정 가능성
③ 구조적/경쟁 리스크: 시장 점유율 위협, 신기술 대체, 경쟁 심화, 산업 사이클 피크
④ 매크로/외부 리스크: 금리·환율·원자재 가격, 규제 환경 변화, 지정학적 불확실성

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 주가, 수익률, 재무 수치 등 모든 숫자는 반드시 제공된 데이터에 명시된 것만 사용하세요. 데이터에 없는 수치를 추정·가정·생성하는 것은 절대 금지입니다.
- 4가지 축 중 가장 중대한 2~3가지를 중심으로 리스크를 분석하세요.
- 과도한 비관론이 아닌 데이터 기반 리스크 분석에 집중하세요.
- 응답 전에 출력의 모든 수치가 위 데이터에서 확인 가능한지 반드시 검토하세요.
- 응답은 반드시 JSON 형식으로 반환하세요.""",

    "extreme": """당신은 강성 약세 신봉자입니다. 어떤 상황에서도 매도/관망 입장을 견지하며, 매수 논거는 과도한 낙관론으로 일축합니다.

[분석 방향]
- 제공된 데이터에서 리스크 신호가 될 수 있는 모든 요소를 최대한 강하게 부각하세요.
- 긍정적 데이터가 있더라도 이면의 위험이나 지속가능성 문제를 제기하세요.
- 매수 논거는 근거가 불충분하거나 단기적 착시에 불과한 것으로 직접 반박하세요.
- 강한 경계 신호와 명확한 매도/관망 주장을 전면에 내세우세요.

[규칙]
- 반드시 제공된 데이터(기사/정량)에서 근거를 찾아 인용하세요. 근거 없는 주장은 금지입니다.
- 모든 수치는 제공된 데이터에 명시된 것만 사용하세요. 추정·가정·생성은 절대 금지입니다.
- 응답은 반드시 JSON 형식으로 반환하세요.""",
}

SYSTEM_PROMPT_BULL      = _BULL_PROMPTS["standard"]
SYSTEM_PROMPT_BEAR      = _BEAR_PROMPTS["standard"]

SYSTEM_PROMPT_MODERATOR = """당신은 주식 투자 토론의 중립적인 사회자(Moderator)입니다.
Bull과 Bear의 토론 내용을 종합하여 균형 잡힌 최종 의견을 제시하는 역할입니다.

[규칙]
- 어느 한쪽 편을 들지 말고 양측 논거를 공정하게 평가하세요.
- Bull의 핵심 근거 요약, Bear의 핵심 리스크 요약을 모두 포함하세요.
- 최종 판단(매수 적극 / 분할 매수 / 관망 / 매도 고려)을 명확히 제시하세요.
- 투자는 본인 책임임을 언급하세요.
- 응답은 반드시 JSON 형식으로 반환하세요."""

SYSTEM_PROMPT_PROFILER = """당신은 독자 맞춤 커뮤니케이션 설계자입니다.
투자 토론 독자의 설문 응답을 읽고, 그 독자에게 어떻게 설명해야 가장 잘 전달될지 '작성 지침'을 만듭니다.
분석의 사실관계나 투자 결론은 절대 바꾸지 않으며, 오직 전달 방식(설명 깊이·용어·톤·예시)만 조정하는 지침을 작성합니다.
응답은 반드시 JSON 형식으로 반환하세요."""


# 역할(role) → system prompt 매핑 (PERSONA_STRENGTH에 따라 변형)
SYSTEM_PROMPTS = {
    "bull":      _BULL_PROMPTS.get(PERSONA_STRENGTH, _BULL_PROMPTS["standard"]),
    "bear":      _BEAR_PROMPTS.get(PERSONA_STRENGTH, _BEAR_PROMPTS["standard"]),
    "moderator": SYSTEM_PROMPT_MODERATOR,
    "profiler":  SYSTEM_PROMPT_PROFILER,
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
    block = f"━━━ 공통 참고 기사 ━━━\n{_fmt_articles(articles_common)}"
    if articles_side:
        block += f"\n\n━━━ {display} 관점 추가 기사 ━━━\n{_fmt_articles(articles_side)}"
    return block


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


def _memory_block(memory_context: str) -> str:
    if not memory_context:
        return ""
    return f"\n\n━━━ 과거 토론 참고 ━━━\n{memory_context}\n(위 과거 토론 결과를 참고하되, 이번 토론의 새 데이터를 우선 근거로 사용하세요.)"


def _own_history_block(own_history: str) -> str:
    """이번 토론에서 자신이 이미 한 발언 + 반복 억제 지시(evidence-log 방식)."""
    if not own_history:
        return ""
    return (
        f"\n\n━━━ 당신이 이번 토론에서 이미 한 발언 ━━━\n{own_history}\n"
        "위는 당신이 앞선 라운드에서 이미 제시한 논점입니다. "
        "이미 제시한 핵심 논점·수치(예: PER)는 새로운 근거나 각도 없이 반복하지 말고, "
        "논의를 다음 단계로 진전시키세요. 동일 수치를 핵심 근거로 다시 꺼내지 마세요."
    )


def _scope_text(round_num: int) -> str:
    if round_num == 1:
        return "정성적 데이터(뉴스 기사)만"
    elif round_num == 2:
        return "정량 데이터(재무/컨센서스/주가)만"
    else:
        return "정성 + 정량 데이터 모두"


def _round_focus(round_num: int, stance: str) -> str:
    if round_num == 1:
        return (
            "사업·제품·촉매·정책/규제·경쟁구도·수급 등 정성 관점에서 논거를 제시하세요. "
            "실적·밸류에이션은 구체 수치 없이 방향과 서사로만 다루세요."
        )
    elif round_num == 2:
        return (
            "펀더멘털 & 비즈니스 퀄리티 관점에서 논거를 제시하세요. "
            "이익의 질(마진 트렌드, ROE, 부채비율)과 경쟁력을 정량 데이터로 논증하세요."
        )
    else:
        return (
            "촉매제 vs 리스크 관점에서 최종 논거를 완성하세요. "
            f"향후 6~12개월 주가 방향을 결정할 핵심 요인을 {stance} 입장에서 종합 정리하세요."
        )


def _evidence_rule(round_num: int) -> str:
    """라운드별 사용 가능한 근거 종류를 강제. R1은 정성만, R2는 정량, R3+는 통합."""
    if round_num == 1:
        return (
            "- 이 라운드는 정성 분석입니다. 사업·제품·촉매·정책/규제·경쟁구도·수급·투자심리 같은 서사적 근거만 사용하세요.\n"
            "- 주가·PER·PBR·영업이익률·ROE·부채비율·EPS·목표주가·상승여력·수익률·주가 등락률 등 정량/밸류에이션 수치는 "
            "기사 본문에 있어도 인용하지 마세요. 수치 대신 '실적 개선 흐름', '수주 모멘텀'처럼 방향과 서사로 서술하세요.\n"
            "  (예: '주가가 66.78% 급등' → '주가가 큰 폭으로 급등', '영업이익률 2.8%' → '낮은 수익성')"
        )
    if round_num == 2:
        return (
            "- 반드시 위 정량 데이터에서 구체적 수치를 인용하여 논거를 뒷받침하세요.\n"
            "- 위 데이터에 없는 수치는 절대 사용하지 마세요."
        )
    return (
        "- 정성 서사와 정량 수치를 함께 사용하되, 위 데이터에서 확인되는 사실만 인용하세요.\n"
        "- 위 데이터에 없는 수치는 절대 사용하지 마세요."
    )


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
    memory_context: str = "",
    user_persona: str = "",
    persona_tier: str = "",
    horizon: str = "",
    own_history: str = "",
) -> str:
    display = ROLE_META[role]["display"]
    stance  = ROLE_META[role]["stance"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round {round_num}
[당신의 역할]: {display} — {stance} 입장
{_persona_block(user_persona)}{_horizon_directive(horizon)}{_memory_block(memory_context)}
{_data_section(role, articles_common, articles_side, quant_text)}{_tools_block(stance, "argue", round_num)}{_own_history_block(own_history)}

{_few_shot_argue(role, persona_tier)}━━━ 지시 ━━━
이번 라운드는 {_scope_text(round_num)}을 근거로 합니다.
{_round_focus(round_num, stance)}
{_evidence_rule(round_num)}{_persona_directive(user_persona)}
{_cot_block_argue(role, stance)}
반드시 JSON 형식으로 응답하세요:
{_output_format_argue()}"""


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
    memory_context: str = "",
    user_persona: str = "",
    persona_tier: str = "",
    horizon: str = "",
    own_history: str = "",
) -> str:
    display       = ROLE_META[role]["display"]
    stance        = ROLE_META[role]["stance"]
    opponent_role = "bear" if role == "bull" else "bull"
    opponent_disp = ROLE_META[opponent_role]["display"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round {round_num}
[당신의 역할]: {display} — {stance} 입장
{_persona_block(user_persona)}{_horizon_directive(horizon)}{_memory_block(memory_context)}
━━━ 반박해야 할 상대({opponent_disp})의 주장 ━━━
{opponent_statement}

{_data_section(role, articles_common, articles_side, quant_text)}{_tools_block(stance, "rebut", round_num)}{_own_history_block(own_history)}

{_few_shot_rebut(persona_tier)}━━━ 지시 ━━━
이번 라운드는 {_scope_text(round_num)}을 근거로 합니다.
위 {opponent_disp}의 주장에 대해 {display}({stance}) 입장에서 반박하세요.
- 반드시 상대 주장의 구체적 논점을 짚어 반박하세요.
- 반박 근거는 위 데이터에서만 가져오세요.
{_evidence_rule(round_num)}{_persona_directive(user_persona)}
{_cot_block_rebut(opponent_disp, stance)}
반드시 JSON 형식으로 응답하세요:
{_output_format_rebut()}"""


# ═════════════════════════════════════════════════════════
# 2.5 research 프롬프트 — upfront 모드 사전 통합 조사
# ═════════════════════════════════════════════════════════
def build_research_prompt(
    role: str,
    topic: str,
    articles_common: list[dict],
    quant_text: str = "",
    memory_context: str = "",
) -> str:
    """upfront 모드: 토론 시작 전 한 측이 자기 입장 근거를 통합 조사하도록 지시.

    _research_with_tools가 뒤에 '리서치 단계 지시'를 덧붙이므로
    여기서는 역할·주제·공통 데이터·조사 목표까지만 제시한다.
    """
    display = ROLE_META[role]["display"]
    stance  = ROLE_META[role]["stance"]

    return f"""[토론 주제]: {topic}
[당신의 역할]: {display} — {stance} 입장
{_memory_block(memory_context)}
{_data_section(role, articles_common, [], quant_text)}

━━━ 사전 조사 목표 ━━━
이번 토론 전체에서 {display}({stance}) 입장을 뒷받침할 근거를 지금 한 번에 모아두세요.
- search_articles(query): {stance} 논거를 강화/검증할 뉴스를 여러 각도로 검색하세요.
- fetch_quant(ticker): 필요 시 정량 데이터를 조회하세요.
앞으로 라운드마다 추가 조사는 없습니다. 지금 모은 근거만으로 전 라운드를 논증하게 됩니다.
검색 결과가 비거나 근거가 부족하면 수치를 지어내지 말고 그대로 두세요."""


# ═════════════════════════════════════════════════════════
# 3. conclude 프롬프트 — 최종 결론 (Round 3)
# ═════════════════════════════════════════════════════════
def build_conclude_prompt(
    role: str,
    topic: str,
    articles_common: list[dict],
    articles_side: list[dict],
    quant_text: str,
    memory_context: str = "",
    user_persona: str = "",
    horizon: str = "",
) -> str:
    display = ROLE_META[role]["display"]
    stance  = ROLE_META[role]["stance"]

    return f"""[토론 주제]: {topic}
[현재 라운드]: Round 3 (최종)
[당신의 역할]: {display} — {stance} 입장
{_persona_block(user_persona)}{_horizon_directive(horizon)}{_memory_block(memory_context)}
{_articles_block(role, articles_common, articles_side)}

{_quant_block(quant_text)}

━━━ 지시 ━━━
이것은 마지막 라운드입니다.
정성 데이터(뉴스)와 정량 데이터(재무/컨센서스/주가) 모두를 종합하여 {display}({stance}) 입장의 **최종 결론**을 제시하세요.
- 핵심 논거를 압축적으로 정리하세요.
- 데이터 근거를 명확히 드러내세요.
- 4~6문장으로 결론을 명확하게.{_persona_directive(user_persona)}

반드시 JSON 형식으로 응답하세요:
{{"content": "최종 결론", "tags": ["핵심 근거 1", "핵심 근거 2", "핵심 근거 3"]}}"""


# ═════════════════════════════════════════════════════════
# 4. reflection 프롬프트 — 자기 검토 및 수정
# ═════════════════════════════════════════════════════════
def _num_check_block(ungrounded_numbers: list[str] | None) -> str:
    if not ungrounded_numbers:
        return ""
    nums = ", ".join(ungrounded_numbers)
    return f"""
[자동 수치 검증 — 결정적 사전검사]
다음 수치는 위 입력 데이터에서 문자열로 찾지 못했습니다: {nums}
→ 각 수치가 실제로 입력 데이터에 있는지 다시 확인하세요. 없으면 제거하거나 데이터에 있는 값으로 수정하세요.
(단, 표현 차이(예: 59만원 ↔ 590,000원)로 인한 오탐일 수 있으니, 실제로 데이터에 있으면 그대로 두세요.)
"""


def build_reflection_prompt(
    role: str,
    stance: str,
    draft: str,
    input_prompt: str,
    ungrounded_numbers: list[str] | None = None,
) -> str:
    return f"""[Self-Reflection: 초안 자기 검토]

아래는 당신이 방금 작성한 초안입니다. 입력 데이터를 기준으로 4가지 기준을 검토하세요.

[당신에게 주어진 입력]
{input_prompt}

[초안]
{draft}
{_num_check_block(ungrounded_numbers)}
[검토 기준]
1. 할루시네이션: 초안의 모든 수치/날짜/사실이 위 입력 데이터에 명시된 것인가?
2. 역할 일관성: {role.upper()}({stance}) 입장을 일관되게 유지했는가?
3. 근거 인용: 주장을 구체적인 수치나 사실로 뒷받침했는가?
4. 논리 비약: 근거에서 결론으로 가는 인과가 데이터로 뒷받침되는가? (예: "A 제도 도입 → 매출 증가"처럼 데이터에 없는 인과를 임의로 연결하지 않았는가?)

문제가 없으면 verdict를 "OK"로 설정하고 content와 tags를 그대로 유지하세요.
문제가 있으면 verdict를 "REVISE"로 설정하고 수정된 내용을 작성하세요.

반드시 JSON으로 응답하세요:
{{"verdict": "OK", "issues": [], "content": "최종 내용", "tags": ["태그1", "태그2", "태그3"]}}"""


# ═════════════════════════════════════════════════════════
# 5. moderator 프롬프트 — 사회자 요약
# ═════════════════════════════════════════════════════════
def build_moderator_prompt(
    topic: str,
    debate_history: list[dict],
    articles_common: list[dict],
    user_persona: str = "",
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
{_persona_block(user_persona)}
━━━ 참고 기사 목록 ━━━
{articles_text}

━━━ 전체 토론 내용 ━━━
{history_text}

위 토론을 종합하여 최종 결론을 JSON 형식으로 제시하세요.
투자 판단(verdict)은 반드시 다음 중 하나로 명시하세요:
매수 적극 | 분할 매수 | 관망 | 매도 고려

data_balance에는 토론에서 인용된 근거(기사·정량 지표) 자체가 어느 쪽 입장에 더 유리한지를 1문장으로 적으세요.
'누가 더 잘 논증했는가'가 아니라 '입력 데이터의 방향성'이며, 양측 근거가 비슷하면 "균형"으로 쓰세요.{_persona_directive(user_persona)}

응답 형식:
{{
  "bull_summary": "Bull 측 핵심 논거 요약 (2~3문장)",
  "bear_summary": "Bear 측 핵심 리스크 요약 (2~3문장)",
  "conclusion":   "최종 종합 의견 (3~4문장)",
  "verdict":      "매수 적극 | 분할 매수 | 관망 | 매도 고려",
  "data_balance": "근거의 방향성 1문장 (예: 정량 지표는 Bull 측에 유리, 기사 근거는 균형)"
}}"""


# ═════════════════════════════════════════════════════════
# 6. convergence 프롬프트 — 동적 라운드 수렴 판정
# ═════════════════════════════════════════════════════════
def build_convergence_prompt(topic: str, debate_history: list[dict]) -> str:
    history_text = "\n\n".join(
        f"[Round {h['round']} - {h['role']}]\n{h['content']}"
        for h in debate_history
    )

    return f"""[토론 주제]: {topic}

━━━ 지금까지의 Bull vs Bear 토론 ━━━
{history_text}

토론을 한 라운드 더 진행할지(미수렴) / 종료할지(수렴) 판단하세요.
판단 기준은 **가장 마지막 라운드**가 그 이전 라운드들 대비 *실질적으로* 새로운 것을 더했는가입니다.

[핵심 규칙] 이미 등장한 수치·목표주가·PER·논점을 다시 인용하는 것은,
표현이 달라도 '반복'으로 간주합니다. 새로운 표현 ≠ 새로운 논거.

→ 수렴(true): 마지막 라운드가 이전 라운드의 논거·수치를 새로운 근거 없이 되풀이하고 있고,
  핵심 쟁점이 이미 양측에서 충분히 맞붙어 더 보탤 새 논점이 없을 때.

→ 미수렴(false): 마지막 라운드에서 이전에 없던 새로운 논거·데이터·반박 각도가 실제로 등장했거나,
  한쪽이 제기한 핵심 쟁점에 상대가 아직 정면으로 답하지 못했을 때.

표현만 바뀌고 내용이 같으면 수렴(true)으로 판단하세요.

반드시 JSON으로 응답하세요:
{{"converged": true 또는 false, "reason": "판단 근거 (1문장)"}}"""


# ═════════════════════════════════════════════════════════
# 7. profile 프롬프트 — 설문 응답 → 독자 맞춤 작성 지침
# ═════════════════════════════════════════════════════════
SURVEY_LABELS = {
    "gender":      "성별",
    "age":         "나이대",
    "experience":  "투자 기간",
    "level":       "자가 평가 수준",
    "terminology": "용어 숙지도",
    "depth":       "선호 설명 깊이",
}


def build_profile_prompt(survey: dict) -> str:
    answers = "\n".join(
        f"- {SURVEY_LABELS.get(k, k)}: {v}"
        for k, v in survey.items() if v and k != "horizon"   # horizon은 톤이 아닌 내용 강조용 → 프로파일러 제외
    ) or "- (응답 없음)"

    return f"""다음은 투자 토론을 읽을 독자의 설문 응답입니다.

━━━ 설문 응답 ━━━
{answers}

위 응답을 바탕으로, 이 독자에게 맞춰 토론 발언/결론을 작성할 때 따라야 할 '독자 프로필' 지침을 만드세요.

[작성 규칙]
- 투자 기간·자가 평가 수준·용어 숙지도·선호 설명 깊이 → 설명의 깊이, 전문용어 사용/풀이 수준, 분석 밀도를 결정하세요.
- 나이대 → 비유나 예시의 톤에만 가볍게 반영하세요.
- 성별 → 분석 내용·투자 판단·결론에 절대 영향을 주지 마세요. (성별로 다른 결론이나 논조를 만들지 마세요.)
- 투자 판단의 객관성은 독자와 무관하게 동일해야 합니다. 달라지는 것은 '전달 방식'뿐입니다.
- 지침은 3~5개의 간결한 불릿으로, "~하세요" 형태의 실행 지시로 작성하세요.

반드시 JSON으로 응답하세요:
{{"profile": "- 지침1\\n- 지침2\\n- 지침3"}}"""
