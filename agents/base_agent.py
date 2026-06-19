"""
agents/base_agent.py — OpenAI 호출 공통 기반

[변경 사항 v2]
- _chat_with_tools에 force_tool 파라미터 추가.
  지정 시 첫 호출에서 해당 도구를 강제 호출하게 함.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from agents.config import MODEL_NAME, RETRY_ATTEMPTS, RETRY_WAIT_SECONDS
from agents.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client: OpenAI | None = None

# tool calling 루프 최대 횟수
MAX_TOOL_ITERATIONS = 3


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

    # ─────────────────────────────────────────────────────
    # 공통 헬퍼: OpenAI 호출 + RateLimitError 재시도
    # ─────────────────────────────────────────────────────
    def _call_openai(
        self,
        messages: list,
        temperature: float,
        tools: list | None = None,
        tool_choice: str | dict | None = None,
    ):
        kwargs = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if tools is not None:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        for attempt in range(RETRY_ATTEMPTS):
            try:
                return self.client.chat.completions.create(**kwargs)
            except RateLimitError:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                wait = RETRY_WAIT_SECONDS[min(attempt, len(RETRY_WAIT_SECONDS) - 1)]
                print(f"  ⚠️  Rate limit — {wait}초 후 재시도 ({attempt + 1}/{RETRY_ATTEMPTS - 1})")
                time.sleep(wait)

    # ─────────────────────────────────────────────────────
    # 기본 _chat (tool 없음, Moderator/기존 호출 호환)
    # ─────────────────────────────────────────────────────
    def _chat(self, user_prompt: str, temperature: float = 0.7) -> dict:
        response = self._call_openai(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=temperature,
        )
        raw = response.choices[0].message.content or ""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"content": raw, "tags": []}

    # ─────────────────────────────────────────────────────
    # _chat_with_tools (Bull/Bear가 사용. tool calling 루프)
    # ─────────────────────────────────────────────────────
    def _chat_with_tools(
        self,
        user_prompt: str,
        temperature: float = 0.7,
        force_tool: str | None = None,
    ) -> dict:
        """
        force_tool: 지정하면 첫 호출에서 해당 도구를 강제 호출 (데모용).
                   None이면 모델 자율 판단.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        for iteration in range(MAX_TOOL_ITERATIONS + 1):
            # 마지막 반복: 도구 차단 → 무조건 최종 JSON 응답
            if iteration >= MAX_TOOL_ITERATIONS:
                tools_param = None
                tool_choice = None
            # 첫 반복 + force_tool 지정 → 강제 호출
            elif iteration == 0 and force_tool:
                tools_param = TOOL_SCHEMAS
                tool_choice = {"type": "function", "function": {"name": force_tool}}
            # 그 외: 자율 판단
            else:
                tools_param = TOOL_SCHEMAS
                tool_choice = "auto"

            response = self._call_openai(messages, temperature, tools=tools_param, tool_choice=tool_choice)
            msg = response.choices[0].message

            # tool 호출이 있으면 실행 후 루프 계속
            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
                for tc in msg.tool_calls:
                    result = self._execute_tool(tc.function.name, tc.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            # tool 호출 없음 → 최종 응답 파싱
            raw = msg.content or ""
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"content": raw, "tags": []}

        return {"content": "", "tags": []}

    # ─────────────────────────────────────────────────────
    @staticmethod
    def _execute_tool(name: str, arguments_json: str) -> str:
        fn = TOOL_FUNCTIONS.get(name)
        if not fn:
            return f"[에러] 알 수 없는 tool: {name}"
        try:
            args = json.loads(arguments_json or "{}")
            result = fn(**args)
            preview = str(args.get("query", ""))[:40]
            print(f"  🔧 [{name}] {preview} → {len(result)}자")
            return result
        except Exception as e:
            return f"[에러] {name} 실행 실패: {e}"
