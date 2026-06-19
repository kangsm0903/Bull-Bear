"""
agents/base_agent.py — OpenAI 호출 공통 기반

이 파일은 LLM 호출 로직만 담당합니다.
모델/온도/재시도 설정은 agents/config.py에서 가져옵니다.
프롬프트는 prompts.py에서 가져옵니다.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from agents.config import (
    MODEL_NAME,
    RETRY_ATTEMPTS,
    RETRY_WAIT_SECONDS,
    TOOL_MAX_CALLS_PER_STEP,
    TOOL_MAX_ROUNDS_PER_STEP,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


class BaseAgent:
    """LLM 호출 기반 클래스. 하위 클래스는 system_prompt와 도메인 메서드를 정의."""

    def __init__(self):
        self.client = get_client()

    @property
    def system_prompt(self) -> str:
        raise NotImplementedError

    def _chat(self, user_prompt: str, temperature: float = 0.7) -> dict:
        """
        GPT 호출 → JSON 응답 dict 반환.
        config.RETRY_ATTEMPTS에 따라 RateLimitError 재시도.
        o1/o3 계열 reasoning 모델은 temperature 대신 reasoning_effort 사용.
        """
        is_reasoning = MODEL_NAME.startswith(("o1", "o3"))

        for attempt in range(RETRY_ATTEMPTS):
            try:
                kwargs = dict(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                if is_reasoning:
                    from agents import config as _cfg
                    effort = getattr(_cfg, "REASONING_EFFORT", "medium")
                    kwargs["reasoning_effort"] = effort
                else:
                    kwargs["temperature"] = temperature

                response = self.client.chat.completions.create(**kwargs)
                raw = response.choices[0].message.content
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"content": raw, "tags": []}

            except RateLimitError:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                wait = RETRY_WAIT_SECONDS[min(attempt, len(RETRY_WAIT_SECONDS) - 1)]
                print(f"  [Rate limit] {wait}s 후 재시도 ({attempt + 1}/{RETRY_ATTEMPTS - 1})")
                time.sleep(wait)

    def _chat_with_tools(
        self,
        user_prompt: str,
        tools: list[dict],
        dispatch,
        temperature: float = 0.7,
        max_tool_rounds: int | None = None,
        max_tool_calls: int | None = None,
    ) -> tuple[dict, list]:
        """
        function calling 루프.
          1. tools를 주고 호출 → 모델이 tool_call을 내면 dispatch로 실행 후 결과 주입.
          2. tool_call이 없으면 그 응답을 최종 답변으로 파싱.
          3. max_tool_rounds 소진 시 tools 없이 JSON 강제 호출로 마무리.
        반환: (답변 dict, 조사한 기사 리스트)
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        collected_articles: list = []
        tool_round_limit = max_tool_rounds if max_tool_rounds is not None else TOOL_MAX_ROUNDS_PER_STEP
        tool_call_limit = max_tool_calls if max_tool_calls is not None else TOOL_MAX_CALLS_PER_STEP
        tool_calls_used = 0
        is_reasoning = MODEL_NAME.startswith(("o1", "o3"))

        for _ in range(tool_round_limit):
            kwargs = dict(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                response_format={"type": "json_object"},
            )
            if is_reasoning:
                from agents import config as _cfg
                kwargs["reasoning_effort"] = getattr(_cfg, "REASONING_EFFORT", "medium")
            else:
                kwargs["temperature"] = temperature

            response = self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            if not msg.tool_calls:
                return _loads(msg.content), collected_articles

            messages.append(msg)
            for tc in msg.tool_calls:
                if tool_calls_used >= tool_call_limit:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "(tool call 한도 초과: 이미 수집한 근거만 사용하세요.)",
                    })
                    continue

                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"  [Tool] {tc.function.name}({args})")
                out = dispatch(tc.function.name, args)
                tool_calls_used += 1
                collected_articles.extend(out.get("articles", []))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out["text"],
                })

        # 도구 한도 소진 → 도구 없이 최종 답변(JSON) 강제
        kwargs = dict(
            model=MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
        )
        if is_reasoning:
            from agents import config as _cfg
            kwargs["reasoning_effort"] = getattr(_cfg, "REASONING_EFFORT", "medium")
        else:
            kwargs["temperature"] = temperature

        response = self.client.chat.completions.create(**kwargs)
        return _loads(response.choices[0].message.content), collected_articles

    def _research_with_tools(
        self,
        user_prompt: str,
        tools: list[dict],
        dispatch,
        cache_key,
        temperature: float = 0.3,
        max_tool_rounds: int | None = None,
        max_tool_calls: int | None = None,
    ) -> tuple[str, list]:
        """
        사전 리서치 전용 function calling 루프.

        최종 발언은 작성하지 않고 tool 결과 텍스트와 검색 기사만 수집한다.
        같은 step 안에서 동일 tool call은 한 번만 실행한다.
        """
        research_prompt = (
            f"{user_prompt}\n\n"
            "━━━ 리서치 단계 지시 ━━━\n"
            "지금은 최종 발언 작성 단계가 아닙니다.\n"
            "필요한 search_articles/fetch_quant 도구만 호출해 근거를 수집하세요.\n"
            '이미 제공된 데이터만으로 충분하면 도구를 호출하지 않고 {"research_complete": true}로 응답하세요.\n'
            "최종 주장/반박 본문은 작성하지 마세요."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user",   "content": research_prompt},
        ]
        collected_articles: list = []
        collected_texts: list[str] = []
        seen_calls: set[str] = set()
        tool_round_limit = max_tool_rounds if max_tool_rounds is not None else TOOL_MAX_ROUNDS_PER_STEP
        tool_call_limit = max_tool_calls if max_tool_calls is not None else TOOL_MAX_CALLS_PER_STEP
        tool_calls_used = 0
        is_reasoning = MODEL_NAME.startswith(("o1", "o3"))

        for _ in range(tool_round_limit):
            kwargs = dict(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                response_format={"type": "json_object"},
            )
            if is_reasoning:
                from agents import config as _cfg
                kwargs["reasoning_effort"] = getattr(_cfg, "REASONING_EFFORT", "medium")
            else:
                kwargs["temperature"] = temperature

            response = self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            if not msg.tool_calls:
                break

            messages.append(msg)
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                key = cache_key(tc.function.name, args)
                if key in seen_calls:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "(중복 tool call 생략: 이전 리서치 결과를 사용하세요.)",
                    })
                    print(f"  [Tool skipped] {tc.function.name}({args})")
                    continue

                if tool_calls_used >= tool_call_limit:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "(tool call 한도 초과: 이미 수집한 근거만 사용하세요.)",
                    })
                    continue

                print(f"  [Research Tool] {tc.function.name}({args})")
                out = dispatch(tc.function.name, args)
                seen_calls.add(key)
                tool_calls_used += 1
                collected_articles.extend(out.get("articles", []))
                collected_texts.append(
                    f"[{tc.function.name} {args}]\n{out['text']}"
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out["text"],
                })

        return "\n\n".join(collected_texts), collected_articles


def _loads(raw: str | None) -> dict:
    """LLM 텍스트 응답을 JSON dict로 파싱. 실패 시 content 폴백."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"content": raw or "", "tags": []}
