"""
agents/profiler.py — 독자 프로파일러 에이전트

토론 시작 전, 사용자의 설문 응답을 읽고 '독자 맞춤 작성 지침(프로필 문자열)'을 1회 생성한다.
이 프로필은 orchestrator를 거쳐 Bull/Bear/Moderator 프롬프트의 _persona_block에 주입된다.

규칙(프롬프트에 명시):
  - 지식 관련 응답(자가 수준/용어 숙지도/설명 깊이) → 설명 깊이·용어·밀도 결정.
  - 투자 판단의 객관성은 독자와 무관하게 동일 (달라지는 것은 전달 방식뿐).
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
        profile = result.get("profile") or ""
        # 모델이 profile을 리스트(불릿 배열)로 반환하는 경우가 있어 문자열로 정규화.
        if isinstance(profile, list):
            profile = "\n".join(str(x) for x in profile)
        return profile.strip()
