"""
agents/profiler.py — 독자 프로파일러 에이전트

토론 시작 전, 사용자의 설문 응답을 읽고 '독자 맞춤 작성 지침(프로필 문자열)'을 1회 생성한다.
이 프로필은 orchestrator를 거쳐 Bull/Bear/Moderator 프롬프트의 _persona_block에 주입된다.

규칙(프롬프트에 명시):
  - 지식 관련 응답(투자 기간/자가 수준/용어 숙지도/설명 깊이) → 설명 깊이·용어·밀도 결정.
  - 나이대 → 톤·예시에만 가볍게 반영.
  - 성별 → 분석 내용·결론에 영향 금지 (편향 방지).
"""

from agents.base_agent import BaseAgent
from agents.config import TEMPERATURE
from agents.prompts import SYSTEM_PROMPTS, build_profile_prompt


class ProfilerAgent(BaseAgent):

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPTS["profiler"]

    def profile(self, survey: dict) -> str:
        """설문 응답 dict → 독자 맞춤 지침 문자열. 응답이 비면 빈 문자열."""
        if not survey or not any(survey.values()):
            return ""
        result = self._chat(
            build_profile_prompt(survey),
            temperature=TEMPERATURE["profiler"],
        )
        return (result.get("profile") or "").strip()
