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
from agents.config import (
    ENABLE_COT,
    ENABLE_REFLECTION,
    ENABLE_TOOL_CALLING,
    RESEARCH_MODE,
    ROLE_META,
    TEMPERATURE,
)
from agents.tools import TOOL_SCHEMAS, cache_key, dispatch, tools_for_round
from agents.verifier import verify_numbers
from agents.prompts import (
    SYSTEM_PROMPTS,
    build_argue_prompt,
    build_conclude_prompt,
    build_rebut_prompt,
    build_reflection_prompt,
    build_research_prompt,
)


def _with_research_context(prompt: str, research_text: str) -> str:
    research_block = research_text.strip() if research_text.strip() else "(추가 리서치 결과 없음)"
    return f"""{prompt}

━━━ 사전 리서치 결과 ━━━
{research_block}

━━━ 최종 발언 작성 지시 ━━━
리서치 단계는 종료되었습니다. 이제 도구를 호출하지 말고 최종 JSON 답변만 작성하세요.
근거는 위 원데이터와 사전 리서치 결과에서 확인되는 사실만 사용하세요."""


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

    # ── 사전 통합 조사 (upfront 모드 전용) ──────────────
    def research(
        self,
        topic: str,
        articles_common: list[dict],
        quant_text: str = "",
        memory_context: str = "",
    ) -> list[dict]:
        """토론 시작 전 자기 입장 근거를 한 번에 조사해 기사 리스트를 반환.

        조사 결과 기사는 이후 라운드에 articles_side로 주입되어 재사용된다.
        (정량 등 텍스트 결과는 라운드의 quant_text/공통 데이터로 충분하므로 버린다.)
        """
        prompt = build_research_prompt(
            role=self.role,
            topic=topic,
            articles_common=articles_common,
            quant_text=quant_text,
            memory_context=memory_context,
        )
        _text, articles = self._research_with_tools(
            prompt, TOOL_SCHEMAS, dispatch, cache_key,
        )
        return articles

    # ── LLM 호출 (조사 방식 분기) ───────────────────────
    def _run_llm(self, prompt: str, temperature: float, can_top_up: bool = False, round_num: int = 0) -> tuple[dict, list, str]:
        """조사 방식에 따라 발언 전 조사 여부를 결정한 뒤 최종 답변 생성.

        - per_step: 모든 발언에서 (필수) 조사.
        - hybrid:   argue는 사전 조사 근거만 사용(can_top_up=False), rebut만 추가 조사(can_top_up=True).
        - upfront/OFF: 발언 중 조사 없음. 근거는 이미 articles_side로 프롬프트에 들어있음.
        반환: (draft dict, 이 발언에서 조사한 기사 리스트, 실제 사용한 프롬프트).
              실제 프롬프트는 조사 결과까지 합친 것으로, Self-Reflection이 같은 근거로 검토하도록 돌려준다.
        """
        do_research = ENABLE_TOOL_CALLING and (
            RESEARCH_MODE == "per_step"
            or (RESEARCH_MODE == "hybrid" and can_top_up)
        )
        if do_research:
            research_text, articles = self._research_with_tools(
                prompt,
                tools_for_round(round_num),
                dispatch,
                cache_key,
                temperature=temperature,
            )
            final_prompt = _with_research_context(prompt, research_text)
            return self._chat(final_prompt, temperature=temperature), articles, final_prompt
        return self._chat(prompt, temperature=temperature), [], prompt

    # ── Self-Reflection ──────────────────────────────────
    def _reflect(self, draft: dict, input_prompt: str) -> dict:
        """초안을 자기 검토하고, 문제가 있으면 수정한 뒤 반환."""
        if not ENABLE_REFLECTION:
            return draft

        stance = ROLE_META[self.role]["stance"]
        # 결정적 수치 검증: 출력 수치 중 입력 데이터에서 못 찾은 것을 reflection에 근거로 제공
        ungrounded = verify_numbers(draft.get("content", ""), input_prompt)
        if ungrounded:
            print(f"  [NumCheck] {self.role.upper()} 미검증 수치: {ungrounded}")
        ref_prompt = build_reflection_prompt(
            role=self.role,
            stance=stance,
            draft=draft.get("content", ""),
            input_prompt=input_prompt,
            ungrounded_numbers=ungrounded,
        )
        result = self._chat(ref_prompt, temperature=TEMPERATURE["reflect"])

        verdict = result.get("verdict", "OK")
        print(f"  [Reflection] {self.role.upper()} → {verdict}"
              + (f" | issues: {result.get('issues', [])}" if verdict == "REVISE" else ""))

        return {
            "content":    result.get("content", draft.get("content", "")),
            "tags":       result.get("tags", draft.get("tags", [])),
            "reasoning":  draft.get("reasoning", ""),
            "reflection": {"verdict": verdict, "issues": result.get("issues", [])},
        }

    # ── 액션 메서드 ─────────────────────────────────────
    def argue(
        self,
        topic: str,
        round_num: int,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str = "",
        memory_context: str = "",
        user_persona: str = "",
        persona_tier: str = "",
        horizon: str = "",
        depth: str = "",
        own_history: str = "",
    ) -> dict:
        prompt = build_argue_prompt(
            role=self.role,
            topic=topic,
            round_num=round_num,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
            memory_context=memory_context,
            user_persona=user_persona,
            persona_tier=persona_tier,
            horizon=horizon,
            depth=depth,
            own_history=own_history,
        )
        draft, articles, eff_prompt = self._run_llm(prompt, TEMPERATURE["argue"], can_top_up=False, round_num=round_num)
        result = self._reflect(draft, eff_prompt)
        result["researched_articles"] = articles
        return result

    def rebut(
        self,
        topic: str,
        round_num: int,
        opponent_statement: str,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str = "",
        memory_context: str = "",
        user_persona: str = "",
        persona_tier: str = "",
        horizon: str = "",
        depth: str = "",
        own_history: str = "",
    ) -> dict:
        prompt = build_rebut_prompt(
            role=self.role,
            topic=topic,
            round_num=round_num,
            opponent_statement=opponent_statement,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
            memory_context=memory_context,
            user_persona=user_persona,
            persona_tier=persona_tier,
            horizon=horizon,
            depth=depth,
            own_history=own_history,
        )
        draft, articles, eff_prompt = self._run_llm(prompt, TEMPERATURE["rebut"], can_top_up=True, round_num=round_num)
        result = self._reflect(draft, eff_prompt)
        result["researched_articles"] = articles
        return result

    def conclude(
        self,
        topic: str,
        articles_common: list[dict],
        articles_side: list[dict],
        quant_text: str,
        memory_context: str = "",
        user_persona: str = "",
        horizon: str = "",
        depth: str = "",
    ) -> dict:
        prompt = build_conclude_prompt(
            role=self.role,
            topic=topic,
            articles_common=articles_common,
            articles_side=articles_side,
            quant_text=quant_text,
            memory_context=memory_context,
            user_persona=user_persona,
            horizon=horizon,
            depth=depth,
        )
        draft = self._chat(prompt, temperature=TEMPERATURE["conclude"])
        return self._reflect(draft, prompt)

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
        memory_context: str = "",
        user_persona: str = "",
        persona_tier: str = "",
        horizon: str = "",
        depth: str = "",
        own_history: str = "",
    ) -> dict:
        if action == "argue":
            return self.argue(topic, round_num, articles_common, articles_side,
                              quant_text, memory_context, user_persona, persona_tier, horizon, depth, own_history)
        if action == "rebut":
            return self.rebut(topic, round_num, opponent_statement,
                              articles_common, articles_side, quant_text,
                              memory_context, user_persona, persona_tier, horizon, depth, own_history)
        if action == "conclude":
            return self.conclude(topic, articles_common, articles_side,
                                 quant_text, memory_context, user_persona, horizon, depth)
        raise ValueError(f"Unknown action: {action}")
