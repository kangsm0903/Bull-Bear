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

from agents.config import MODEL_NAME, RETRY_ATTEMPTS, RETRY_WAIT_SECONDS

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
        """
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                raw = response.choices[0].message.content
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"content": raw, "tags": []}

            except RateLimitError:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                wait = RETRY_WAIT_SECONDS[min(attempt, len(RETRY_WAIT_SECONDS) - 1)]
                print(f"  ⚠️  Rate limit — {wait}초 후 재시도 ({attempt + 1}/{RETRY_ATTEMPTS - 1})")
                time.sleep(wait)
