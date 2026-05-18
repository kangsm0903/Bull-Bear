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
from agents.moderator import ModeratorAgent
from agents.config import DEBATE_FLOW, TOP_K_COMMON, TOP_K_SIDE
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

    # ─────────────────────────────────────────────────────
    def run(self, topic: str, on_round_complete=None) -> dict:
        # ── 1. 데이터 준비 ────────────────────────────
        queries = expand_query(topic)
        articles_common = search(queries["common"], source="articles", top_k=TOP_K_COMMON)
        articles_bull   = search(queries["bull"],   source="articles", top_k=TOP_K_SIDE)
        articles_bear   = search(queries["bear"],   source="articles", top_k=TOP_K_SIDE)

        detected_ticker = _detect_ticker(topic)
        quant_data = fetch_quant(detected_ticker) if detected_ticker else None
        quant_text = format_quant(quant_data) if quant_data else ""

        articles_by_side = {
            "bull": articles_bull,
            "bear": articles_bear,
        }

        # ── 2. 라운드별 실행 ──────────────────────────
        all_rounds: list[list[dict]] = []
        for round_cfg in DEBATE_FLOW:
            round_msgs = self._run_round(
                round_cfg=round_cfg,
                topic=topic,
                articles_common=articles_common,
                articles_by_side=articles_by_side,
                quant_text=quant_text,
            )
            all_rounds.append(round_msgs)
            if on_round_complete:
                on_round_complete(round_cfg["round"], round_msgs)

        # ── 3. Moderator 결론 ─────────────────────────
        moderator_history = [
            {"round": m["round"], "role": m["role"].capitalize(), "content": m["content"]}
            for round_msgs in all_rounds for m in round_msgs
        ]
        moderator_result = self.moderator.conclude(
            topic=topic,
            debate_history=moderator_history,
            articles_common=articles_common,
        )

        return {
            "topic": topic,
            "rounds": all_rounds,
            "moderator": moderator_result,
            "articles": {
                "common": articles_common,
                "bull":   articles_bull,
                "bear":   articles_bear,
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


# ═════════════════════════════════════════════════════════
# 내부 헬퍼
# ═════════════════════════════════════════════════════════
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
    }
