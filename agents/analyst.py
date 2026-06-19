"""
agents/analyst.py — Bull/Bear 통합 애널리스트 에이전트

[변경 사항 v2]
- argue 메서드에서 round_num == 1 일 때 search_web_news를 강제 호출.
  (데모 목적: 첫 라운드에서 무조건 최신 웹 뉴스 1회 가져오기)
- rebut, conclude는 모델 자율 판단.
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
        # 데모 목적: Round 1 argue에서는 무조건 웹검색 1회 강제
        force = "search_web_news" if round_num == 1 else None
        return self._chat_with_tools(prompt, temperature=TEMPERATURE["argue"], force_tool=force)

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
        return self._chat_with_tools(prompt, temperature=TEMPERATURE["rebut"])

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
        return self._chat_with_tools(prompt, temperature=TEMPERATURE["conclude"])

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
