"""
agents/analyst.py — Bull/Bear 통합 애널리스트 에이전트

Bull과 Bear는 system_prompt와 입력 데이터만 다르고 호출 구조가 동일합니다.
하나의 클래스에 role 파라미터로 통합합니다.

세 가지 액션:
  - argue:    독립 주장
  - rebut:    상대 주장에 대한 반론
  - conclude: 최종 결론 (Round 3)
"""

from agents.base_agent import BaseAgent
from agents.config import TEMPERATURE
from agents.prompts import (
    SYSTEM_PROMPTS,
    build_argue_prompt,
    build_rebut_prompt,
    build_conclude_prompt,
)


class AnalystAgent(BaseAgent):
    """Bull 또는 Bear 애널리스트. role로 지정."""

    def __init__(self, role: str):
        if role not in ("bull", "bear"):
            raise ValueError(f"role must be 'bull' or 'bear', got: {role}")
        self.role = role
        super().__init__()

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPTS[self.role]

    # ── 액션 메서드 ─────────────────────────────────────
    def argue(
        self,
        topic: str,
        round_num: int,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str = "",
    ) -> dict:
        prompt = build_argue_prompt(
            role=self.role,
            topic=topic,
            round_num=round_num,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
        )
        return self._chat(prompt, temperature=TEMPERATURE["argue"])

    def rebut(
        self,
        topic: str,
        round_num: int,
        opponent_statement: str,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str = "",
    ) -> dict:
        prompt = build_rebut_prompt(
            role=self.role,
            topic=topic,
            round_num=round_num,
            opponent_statement=opponent_statement,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
        )
        return self._chat(prompt, temperature=TEMPERATURE["rebut"])

    def conclude(
        self,
        topic: str,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str,
    ) -> dict:
        prompt = build_conclude_prompt(
            role=self.role,
            topic=topic,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
        )
        return self._chat(prompt, temperature=TEMPERATURE["conclude"])

    # ── action 이름으로 디스패치 (orchestrator가 사용) ─
    def run_action(
        self,
        action: str,
        *,
        topic: str,
        round_num: int,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str,
        opponent_statement: str = "",
    ) -> dict:
        if action == "argue":
            return self.argue(topic, round_num, articles_common, articles_side, quant_text)
        if action == "rebut":
            return self.rebut(topic, round_num, opponent_statement,
                              articles_common, articles_side, quant_text)
        if action == "conclude":
            return self.conclude(topic, articles_common, articles_side, quant_text)
        raise ValueError(f"Unknown action: {action}")
