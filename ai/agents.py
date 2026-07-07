import json

from config import MODEL, client


BULL_SYSTEM_PROMPT = """
너는 'Bull'이라는 낙관적인 주식 분석가다.
주어진 종목에 대해 '상승(강세)' 입장에서 논리를 편다.

규칙:
- 실적 개선, 성장 잠재력, 수급, 산업 전망 등 긍정적 근거를 제시한다.
- 막연한 낙관이 아니라, 구체적이고 설득력 있게 주장한다.
- 한국어로, 3~4문장으로 간결하게 말한다.
"""


BEAR_SYSTEM_PROMPT = """
너는 'Bear'이라는 신중하고 비판적인 주식 분석가다.
주어진 종목에 대해 '하락(약세)' 입장에서 논리를 편다.

규칙:
- 밸류에이션 부담, 실적 둔화, 경쟁 심화, 거시 리스크 등 부정적 근거를 제시한다.
- 막연한 비관이 아니라, 구체적이고 설득력 있게 주장한다.
- 한국어로, 3~4문장으로 간결하게 말한다.
"""


MODERATOR_SYSTEM_PROMPT = """
너는 중립적인 토론 사회자(Moderator)다.
Bull(상승론)과 Bear(하락론)의 주장을 모두 읽고 공정하게 평가한다.

반드시 아래 형식의 JSON만 출력한다:
{
    "bull_summary": "Bull 주장 한 문장 요약",
    "bear_summary": "Bear 주장 한 문장 요약",
    "conclusion": "양측을 종합한 중립적 결론 2~3문장",
    "verdict": "다음 넷 중 하나만: 매수 적극 | 분할 매수 | 관망 | 매도 고려",
    "data_balance": "어느 쪽 논리가 더 설득력 있었는지 한 문장"
}

규칙:
- 한쪽 편을 들지 말고 중립적으로 판단한다.
- verdict는 반드시 위 네 가지 중 하나를 그대로 쓴다.
- 모든 값은 한국어로 작성한다.
"""


def run_bull(topic: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": BULL_SYSTEM_PROMPT},
            {"role": "user", "content": f"종목: {topic}\n이 종목의 상승 논리를 펼쳐줘."},
        ],
    )
    return response.choices[0].message.content


def run_bear(topic: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": BEAR_SYSTEM_PROMPT},
            {"role": "user", "content": f"종목: {topic}\n이 종목의 하락 논리를 펼쳐줘."},
        ],
    )
    return response.choices[0].message.content


def run_moderator(topic: str, bull_argument: str, bear_argument: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MODERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"종목: {topic}\n\n"
                f"[Bull 주장]\n{bull_argument}\n\n"
                f"[Bear 주장]\n{bear_argument}\n\n"
                "위 두 주장을 평가해줘."
            )},
        ],
    )
    return json.loads(response.choices[0].message.content)
