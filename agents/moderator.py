"""
agents/moderator.py — 사회자 에이전트

전체 토론을 종합해 최종 결론을 도출.
프롬프트는 prompts.py에서 가져옵니다.
"""

from agents.base_agent import BaseAgent
from agents.config import TEMPERATURE
from agents.prompts import (
    SYSTEM_PROMPTS,
    build_convergence_prompt,
    build_moderator_prompt,
)


class ModeratorAgent(BaseAgent):

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPTS["moderator"]

    def conclude(
        self,
        topic: str,
        debate_history: list[dict],
        articles_common: list[dict],
        user_persona: str = "",
    ) -> dict:
        prompt = build_moderator_prompt(
            topic=topic,
            debate_history=debate_history,
            articles_common=articles_common,
            user_persona=user_persona,
        )
        return self._chat(prompt, temperature=TEMPERATURE["moderator"])

    def check_convergence(self, topic: str, debate_history: list[dict]) -> dict:
        """지금까지의 토론이 수렴했는지 판정. {'converged': bool, 'reason': str} 반환."""
        prompt = build_convergence_prompt(topic=topic, debate_history=debate_history)
        result = self._chat(prompt, temperature=TEMPERATURE["convergence"])
        return {
            "converged": bool(result.get("converged", False)),
            "reason":    result.get("reason", ""),
        }
