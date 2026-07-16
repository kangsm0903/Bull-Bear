import json

from config import MODEL, client
from news import search_news


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


# ── search_news 도구 명세: AI에게 "이런 함수 쓸 수 있어"라고 알려주는 설명서 ──
SEARCH_NEWS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_news",
        "description": "이 종목의 최근 뉴스 기사를 검색한다. 주장의 근거가 될 기사를 찾을 때 사용.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "검색 키워드(예: 'HBM', '실적', '배당'). 비우면 최신 기사 전체.",
                },
            },
            "required": [],
        },
    },
}


def _run_agent_with_tools(system_prompt: str, user_prompt: str, ticker: str,
                          agent_name: str) -> tuple[str, list[dict]]:
    """에이전트를 실행하되, 필요하면 search_news를 호출하게 한다.
    최종 답변 텍스트와, 그 과정에서 가져온 기사 목록을 함께 반환한다."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    used_articles: list[dict] = []

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[SEARCH_NEWS_TOOL],   # 쓸 수 있는 도구 목록을 알려줌
        )
        message = response.choices[0].message

        # 도구 호출 요청이 없으면 = 최종 답변 → 종료
        if not message.tool_calls:
            return message.content, used_articles

        # 도구를 요청했으면: 그 요청 메시지를 대화에 기록하고
        messages.append(message)
        for call in message.tool_calls:
            args = json.loads(call.function.arguments)      # AI가 넘긴 인자(JSON)
            keyword = args.get("keyword", "")
            articles = search_news(ticker, keyword)
            used_articles.extend(articles)

            # 어떤 키워드로 무슨 기사를 가져왔는지 로그
            print(f"[{agent_name}] 🔍 search_news(keyword={keyword!r}) → {len(articles)}건")
            for a in articles:
                print(f"    - {a['title'][:50]} ({a['published_at']})")

            # 실행 결과를 'tool' 역할 메시지로 AI에게 돌려줌
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(articles, ensure_ascii=False),
            })


def run_bull(topic: str, ticker: str) -> tuple[str, list[dict]]:
    user_prompt = f"종목: {topic}\n뉴스를 검색해 근거로 삼아, 이 종목의 상승 논리를 펼쳐줘."
    return _run_agent_with_tools(BULL_SYSTEM_PROMPT, user_prompt, ticker, "🐂 Bull")


def run_bear(topic: str, ticker: str) -> tuple[str, list[dict]]:
    user_prompt = f"종목: {topic}\n뉴스를 검색해 근거로 삼아, 이 종목의 하락 논리를 펼쳐줘."
    return _run_agent_with_tools(BEAR_SYSTEM_PROMPT, user_prompt, ticker, "🐻 Bear")


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
