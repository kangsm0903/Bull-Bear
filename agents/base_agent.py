"""
BaseAgent — OpenAI GPT 호출 공통 기반
모든 Agent(Bull, Bear, Moderator)가 상속
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

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
    """
    GPT 호출 기반 클래스.
    system_prompt는 각 하위 클래스에서 정의.
    """

    MODEL = "gpt-4o"

    def __init__(self):
        self.client = get_client()

    @property
    def system_prompt(self) -> str:
        raise NotImplementedError

    def _chat(self, user_prompt: str, temperature: float = 0.7) -> dict:
        """
        GPT 호출 → JSON 응답 반환.
        RateLimitError 발생 시 최대 3회 재시도 (5초 간격)
        """
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.MODEL,
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

            except RateLimitError as e:
                if attempt == 2:
                    raise
                wait = 10 * (attempt + 1)  # 10초, 20초
                print(f"  ⚠️  Rate limit — {wait}초 후 재시도 ({attempt + 1}/2)")
                time.sleep(wait)
