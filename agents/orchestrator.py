"""
agents/orchestrator.py — 토론 흐름 실행 엔진

이 파일은 로직만 담당합니다. 발언 순서/모델/온도는 config.py에서 가져옵니다.
프롬프트는 prompts.py를 통해 분리되어 있습니다.

알고리즘:
  1. config.DEBATE_FLOW의 각 라운드를 순회.
  2. 라운드 내 step들을 의존성 레벨로 분류:
       Level 0: argue/conclude (의존성 없음)
       Level 1+: rebut (Level 0의 결과를 입력으로 받음)
  3. 같은 레벨은 ThreadPoolExecutor로 병렬 호출.
  4. 출력은 DEBATE_FLOW에 선언된 step 순서대로 정렬.
"""

from concurrent.futures import ThreadPoolExecutor

from agents.analyst import AnalystAgent
from agents.memory import DebateMemory
from agents.moderator import ModeratorAgent
from agents.profiler import ProfilerAgent
from agents.config import (
    DEBATE_FLOW,
    ENABLE_DYNAMIC_ROUNDS,
    ENABLE_TOOL_CALLING,
    FREE_DEBATE_ROUND,
    MAX_DEBATE_ROUNDS,
    RAG_MIN_SCORE,
    RESEARCH_MODE,
    TOP_K_COMMON,
    TOP_K_SIDE,
    TOOL_MAX_ARTICLES_PER_SIDE,
)
from agents.prompts import resolve_persona_tier
from agents.query_expander import expand_query
from rag.retriever import search, _detect_ticker
from rag.quant_fetcher import fetch_quant, format_quant


class DebateOrchestrator:

    def __init__(self):
        self.agents = {
            "bull": AnalystAgent("bull"),
            "bear": AnalystAgent("bear"),
        }
        self.moderator = ModeratorAgent()
        self.profiler = ProfilerAgent()
        self.memory = DebateMemory()

    # ─────────────────────────────────────────────────────
    def run(
        self,
        topic: str,
        on_round_complete=None,
        user_persona: str = "",
        survey: dict | None = None,
    ) -> dict:
        # ── 0. 설문 → 독자 프로필 생성 (설문이 있고 명시 페르소나가 없을 때) ──
        if survey and not user_persona:
            user_persona = self.profiler.profile(survey)
            if user_persona:
                print("  [Profiler] 설문 기반 독자 프로필 생성 완료")

        # few-shot 변형 선택용 독자 등급 (설문 규칙 → 없으면 프리셋 키)
        persona_tier = resolve_persona_tier(user_persona, survey)
        if persona_tier:
            print(f"  [Persona] tier = {persona_tier}")

        # 희망 투자기간 (설문에서) → 근거 강조용. 최종 판단·수치는 불변.
        horizon = (survey or {}).get("horizon", "")
        if horizon:
            print(f"  [Persona] horizon = {horizon}")

        # 선호 설명 깊이 (설문에서) → 답변 분량 조절. 최종 판단·수치는 불변.
        depth = (survey or {}).get("depth", "")
        if depth:
            print(f"  [Persona] depth = {depth}")

        # ── 1. 데이터 준비 ────────────────────────────
        queries = expand_query(topic)
        articles_common = search(queries["common"], source="articles", top_k=TOP_K_COMMON, min_score=RAG_MIN_SCORE)

        detected_ticker = _detect_ticker(topic)
        quant_data = fetch_quant(detected_ticker) if detected_ticker else None
        quant_text = format_quant(quant_data) if quant_data else ""

        # side 기사 출처 (조사 방식에 따라 달라짐):
        #   per_step : 각 발언에서 직접 조사하므로 여기선 빈 채로 둔다.
        #   upfront  : 토론 전 각 측이 1회 통합 조사 (메모리 검색 후 아래에서 채움).
        #   OFF      : 기존처럼 스탠스별 기사를 미리 검색해 떠먹여준다 (off-path 호환).
        if ENABLE_TOOL_CALLING:
            articles_by_side = {"bull": [], "bear": []}
        else:
            articles_by_side = {
                "bull": search(queries["bull"], source="articles", top_k=TOP_K_SIDE, min_score=RAG_MIN_SCORE),
                "bear": search(queries["bear"], source="articles", top_k=TOP_K_SIDE, min_score=RAG_MIN_SCORE),
            }

        # ── 2. 메모리 검색 ────────────────────────────
        past_debates = self.memory.search(ticker=detected_ticker or "", topic=topic)
        memory_context = self.memory.format(past_debates)
        if past_debates:
            print(f"  [Memory] 과거 토론 {len(past_debates)}건 참조")

        # upfront/hybrid 모드: 토론 전 각 측이 자기 입장 근거를 1회 통합 조사.
        if ENABLE_TOOL_CALLING and RESEARCH_MODE in ("upfront", "hybrid"):
            articles_by_side = self._run_upfront_research(
                topic=topic,
                articles_common=articles_common,
                quant_text=quant_text,
                memory_context=memory_context,
            )

        # ── 3. 라운드별 실행 ──────────────────────────
        if ENABLE_DYNAMIC_ROUNDS:
            all_rounds = self._run_dynamic_rounds(
                topic=topic,
                articles_common=articles_common,
                articles_by_side=articles_by_side,
                quant_text=quant_text,
                memory_context=memory_context,
                user_persona=user_persona,
                persona_tier=persona_tier,
                horizon=horizon,
                depth=depth,
                on_round_complete=on_round_complete,
            )
        else:
            all_rounds = []
            for round_cfg in DEBATE_FLOW:
                round_msgs = self._run_round(
                    round_cfg=round_cfg,
                    topic=topic,
                    articles_common=articles_common,
                    articles_by_side=articles_by_side,
                    quant_text=quant_text,
                    memory_context=memory_context,
                    user_persona=user_persona,
                    persona_tier=persona_tier,
                    horizon=horizon,
                    depth=depth,
                    prior_rounds=all_rounds,
                )
                all_rounds.append(round_msgs)
                if on_round_complete:
                    on_round_complete(round_cfg["round"], round_msgs)

        # ── 4. Moderator 결론 ─────────────────────────
        moderator_history = [
            {"round": m["round"], "role": m["role"].capitalize(), "content": m["content"]}
            for round_msgs in all_rounds for m in round_msgs
        ]
        moderator_result = self.moderator.conclude(
            topic=topic,
            debate_history=moderator_history,
            articles_common=articles_common,
            user_persona=user_persona,
        )

        # ── 5. 메모리 저장 ────────────────────────────
        self.memory.save(
            topic=topic,
            ticker=detected_ticker or "",
            moderator_result=moderator_result,
        )

        # ── 6. 페르소나 설정 시 면책 고지 주입 ──
        # (역할 레이블 _inject_context는 UI 말풍선/CLI가 이미 Bull/Bear를 표시해 중복이므로 호출하지 않음)
        if user_persona:
            moderator_result = _inject_disclaimer(moderator_result)

        # 사이드바용 side 기사:
        #   per_step : 라운드 step들에서 조사한 기사를 모아 중복 제거.
        #   hybrid   : upfront 사전 조사 + 발언 중 추가 조사를 병합.
        #   upfront/OFF : 이미 articles_by_side에 채워진 기사를 그대로 사용.
        if ENABLE_TOOL_CALLING and RESEARCH_MODE == "per_step":
            side_articles = _collect_researched(all_rounds)
        elif ENABLE_TOOL_CALLING and RESEARCH_MODE == "hybrid":
            side_articles = _merge_sides(articles_by_side, _collect_researched(all_rounds))
        else:
            side_articles = articles_by_side

        return {
            "topic": topic,
            "rounds": all_rounds,
            "moderator": moderator_result,
            "articles": {
                "common": articles_common,
                "bull":   side_articles["bull"],
                "bear":   side_articles["bear"],
            },
        }

    # ─────────────────────────────────────────────────────
    def _run_round(
        self,
        round_cfg: dict,
        topic: str,
        articles_common: list[dict],
        articles_by_side: dict[str, list[dict]],
        quant_text: str,
        memory_context: str = "",
        user_persona: str = "",
        persona_tier: str = "",
        horizon: str = "",
        depth: str = "",
        prior_rounds: list[list[dict]] | None = None,
    ) -> list[dict]:
        """한 라운드 실행. 의존성 레벨별로 병렬 호출."""
        round_num = round_cfg["round"]
        steps     = round_cfg["steps"]
        use_articles = "articles" in round_cfg["data"]
        use_quant    = "quant"    in round_cfg["data"]

        # 라운드별 데이터 결정
        eff_articles_common = articles_common if use_articles else []
        eff_quant_text      = quant_text      if use_quant    else ""

        # step 호출 콘텍스트
        def call_step(step: dict, prior_results: dict[int, dict]) -> dict:
            role = step["role"]
            agent = self.agents[role]
            opponent_statement = ""
            if step["action"] == "rebut":
                opponent_idx = _find_step(steps, *step["rebuts"])
                if opponent_idx is not None and opponent_idx in prior_results:
                    opponent_statement = prior_results[opponent_idx].get("content", "")
            return agent.run_action(
                action=step["action"],
                topic=topic,
                round_num=round_num,
                articles_common=eff_articles_common,
                articles_side=articles_by_side[role] if use_articles else [],
                quant_text=eff_quant_text,
                opponent_statement=opponent_statement,
                memory_context=memory_context,
                user_persona=user_persona,
                persona_tier=persona_tier,
                horizon=horizon,
                depth=depth,
                own_history=_own_history(prior_rounds, role),
            )

        # 의존성 레벨 계산
        levels = _compute_levels(steps)

        # 레벨별 순차 실행, 같은 레벨은 병렬
        results: dict[int, dict] = {}
        for level_indices in levels:
            with ThreadPoolExecutor(max_workers=max(len(level_indices), 1)) as ex:
                future_to_idx = {
                    ex.submit(call_step, steps[i], results): i
                    for i in level_indices
                }
                for future in future_to_idx:
                    idx = future_to_idx[future]
                    results[idx] = future.result()

        # DEBATE_FLOW에 선언된 step 순서대로 정렬해서 반환
        return [
            _to_message(round_num, steps[i], results[i])
            for i in range(len(steps))
        ]

    # ─────────────────────────────────────────────────────
    def _run_dynamic_rounds(
        self,
        *,
        topic: str,
        articles_common: list[dict],
        articles_by_side: dict[str, list[dict]],
        quant_text: str,
        memory_context: str,
        user_persona: str,
        persona_tier: str = "",
        horizon: str = "",
        depth: str = "",
        on_round_complete=None,
    ) -> list[list[dict]]:
        """
        동적 라운드 실행:
          1. 고정 토론 라운드(정성 → 정량)를 먼저 실행.
          2. 수렴 판정이 '미수렴'이면 자유 토론 라운드를 MAX_DEBATE_ROUNDS 한도까지 반복.
          3. 마지막에 결론 라운드를 실행.
        """
        debate_rounds   = [r for r in DEBATE_FLOW if not _is_conclude_round(r)]
        conclude_rounds = [r for r in DEBATE_FLOW if _is_conclude_round(r)]

        all_rounds: list[list[dict]] = []
        num = 0

        def run_and_collect(round_cfg: dict) -> None:
            nonlocal num
            num += 1
            round_msgs = self._run_round(
                round_cfg={**round_cfg, "round": num},
                topic=topic,
                articles_common=articles_common,
                articles_by_side=articles_by_side,
                quant_text=quant_text,
                memory_context=memory_context,
                user_persona=user_persona,
                persona_tier=persona_tier,
                horizon=horizon,
                depth=depth,
                prior_rounds=all_rounds,
            )
            all_rounds.append(round_msgs)
            if on_round_complete:
                on_round_complete(num, round_msgs)

        # 1) 고정 토론 라운드 (정성 → 정량)
        for round_cfg in debate_rounds:
            run_and_collect(round_cfg)

        # 2) 수렴 판정 → 미수렴이면 자유 토론 라운드 반복 (상한 MAX_DEBATE_ROUNDS)
        for _ in range(MAX_DEBATE_ROUNDS):
            verdict = self.moderator.check_convergence(topic, _flatten_history(all_rounds))
            status = "수렴(종료)" if verdict["converged"] else "미수렴(연장)"
            print(f"  [Convergence] R{num} 후 → {status} | {verdict.get('reason', '')}")
            if verdict["converged"]:
                break
            run_and_collect(FREE_DEBATE_ROUND)

        # 3) 결론 라운드
        for round_cfg in conclude_rounds:
            run_and_collect(round_cfg)

        return all_rounds

    # ─────────────────────────────────────────────────────
    def _run_upfront_research(
        self,
        *,
        topic: str,
        articles_common: list[dict],
        quant_text: str,
        memory_context: str,
    ) -> dict[str, list[dict]]:
        """upfront 모드: bull/bear가 각자 1회 통합 조사 (병렬). url/title 기준 중복 제거 + 상한."""
        def do_research(role: str) -> list[dict]:
            return self.agents[role].research(
                topic=topic,
                articles_common=articles_common,
                quant_text=quant_text,
                memory_context=memory_context,
            )

        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(do_research, role): role for role in ("bull", "bear")}
            raw = {futures[f]: f.result() for f in futures}

        result: dict[str, list[dict]] = {}
        for role, articles in raw.items():
            seen: set = set()
            deduped: list[dict] = []
            for a in articles:
                key = a.get("url") or a.get("title")
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(a)
                if len(deduped) >= TOOL_MAX_ARTICLES_PER_SIDE:
                    break
            result[role] = deduped
            print(f"  [Upfront research] {role.upper()} → {len(deduped)}건 조사")
        return result


# ═════════════════════════════════════════════════════════
# 내부 헬퍼
# ═════════════════════════════════════════════════════════
def _is_conclude_round(round_cfg: dict) -> bool:
    """모든 step의 action이 conclude면 결론 라운드."""
    return all(s["action"] == "conclude" for s in round_cfg["steps"])


def _flatten_history(all_rounds: list[list[dict]]) -> list[dict]:
    """수렴 판정용: 라운드별 메시지 리스트를 평탄화."""
    return [
        {"round": m["round"], "role": m["role"].capitalize(), "content": m["content"]}
        for round_msgs in all_rounds for m in round_msgs
    ]
def _own_history(prior_rounds: list[list[dict]] | None, role: str) -> str:
    """이전 라운드에서 해당 role이 직접 한 발언만 모아 압축 문자열로 (반복 억제용)."""
    if not prior_rounds:
        return ""
    lines = [
        f"[R{m.get('round')} {m.get('kind', '')}] {m['content']}"
        for round_msgs in prior_rounds for m in round_msgs
        if m.get("role") == role and m.get("content")
    ]
    return "\n\n".join(lines)


def _find_step(steps: list[dict], target_role: str, target_action: str) -> int | None:
    """주어진 (role, action)에 매칭되는 step의 index 반환."""
    for i, s in enumerate(steps):
        if s["role"] == target_role and s["action"] == target_action:
            return i
    return None


def _compute_levels(steps: list[dict]) -> list[list[int]]:
    """
    step들을 의존성 레벨로 그룹화.
    Level 0: rebut이 아닌 step (의존성 없음)
    Level N: 의존하는 step의 레벨 + 1
    """
    level_of: dict[int, int] = {}
    for i, step in enumerate(steps):
        if step["action"] != "rebut":
            level_of[i] = 0
        else:
            target = _find_step(steps, *step["rebuts"])
            level_of[i] = (level_of.get(target, -1) + 1) if target is not None else 1

    max_level = max(level_of.values(), default=0)
    groups: list[list[int]] = [[] for _ in range(max_level + 1)]
    for i, lvl in level_of.items():
        groups[lvl].append(i)
    return groups


def _to_message(round_num: int, step: dict, result: dict) -> dict:
    """에이전트 결과를 메시지 dict로 변환."""
    return {
        "round":   round_num,
        "role":    step["role"],          # 'bull' | 'bear'
        "kind":    step["action"],        # 'argue' | 'rebut' | 'conclude'
        "content": result.get("content", ""),
        "tags":    result.get("tags", []),
        "researched_articles": result.get("researched_articles", []),
    }


def _collect_researched(all_rounds: list[list[dict]]) -> dict[str, list[dict]]:
    """라운드 전체에서 bull/bear가 조사한 기사를 모아 url(또는 title) 기준 중복 제거."""
    by_side: dict[str, list[dict]] = {"bull": [], "bear": []}
    seen: dict[str, set] = {"bull": set(), "bear": set()}
    for round_msgs in all_rounds:
        for m in round_msgs:
            role = m.get("role")
            if role not in by_side:
                continue
            if len(by_side[role]) >= TOOL_MAX_ARTICLES_PER_SIDE:
                continue
            for a in m.get("researched_articles", []):
                key = a.get("url") or a.get("title")
                if key and key not in seen[role]:
                    seen[role].add(key)
                    by_side[role].append(a)
                    if len(by_side[role]) >= TOOL_MAX_ARTICLES_PER_SIDE:
                        break
    return by_side


def _merge_sides(*side_dicts: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """여러 {bull/bear: [기사]} dict를 role별로 합치고 url(또는 title) 기준 중복 제거 + 상한."""
    merged: dict[str, list[dict]] = {"bull": [], "bear": []}
    for role in merged:
        seen: set = set()
        for d in side_dicts:
            for a in d.get(role, []):
                key = a.get("url") or a.get("title")
                if key and key not in seen:
                    seen.add(key)
                    merged[role].append(a)
                if len(merged[role]) >= TOOL_MAX_ARTICLES_PER_SIDE:
                    break
    return merged


_ROLE_LABEL = {
    "bull": "[매수(Bull) 측 주장]",
    "bear": "[매도(Bear) 측 주장]",
}

DISCLAIMER = (
    "※ 본 분석은 AI가 생성한 참고 자료입니다. "
    "위 내용은 매수/매도 양측의 주장을 각각 제시한 것이며, "
    "투자 결정의 최종 책임은 본인에게 있습니다."
)


def _inject_context(all_rounds: list[list[dict]]) -> list[list[dict]]:
    """각 메시지 content 앞에 역할 맥락 레이블을 붙인다."""
    result = []
    for round_msgs in all_rounds:
        new_msgs = []
        for msg in round_msgs:
            label = _ROLE_LABEL.get(msg["role"], "")
            new_msg = dict(msg)
            if label:
                new_msg["content"] = f"{label}\n{msg['content']}"
            new_msgs.append(new_msg)
        result.append(new_msgs)
    return result


def _inject_disclaimer(moderator_result: dict) -> dict:
    """moderator 결론 뒤에 면책 고지를 추가한다."""
    result = dict(moderator_result)
    conclusion = result.get("conclusion", "")
    result["conclusion"] = f"{conclusion}\n\n{DISCLAIMER}"
    return result
