"""
agents/orchestrator.py — 토론 흐름 실행 엔진

[변경 사항 v2]
- 토론 시작 시 tools.clear_session_articles() 호출 (컨테이너 초기화).
- 토론 끝에 tools.get_session_articles()로 가져와 articles.common에 합쳐 UI에 노출.
- UI(Source Materials)에서 웹검색으로 추가된 기사도 함께 표시됨.
"""

from concurrent.futures import ThreadPoolExecutor

from agents.analyst import AnalystAgent
from agents.moderator import ModeratorAgent
from agents.config import DEBATE_FLOW, TOP_K_COMMON, TOP_K_SIDE
from agents.query_expander import expand_query
from agents.tools import clear_session_articles, get_session_articles
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
        # ── 0. 세션 초기화 (tool 컨테이너 비우기) ────
        clear_session_articles()

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

        # ── 4. tool로 가져온 기사 합치기 ──────────────
        # search_web_news로 토론 중 가져온 새 기사들을 UI에 노출
        tool_fetched = get_session_articles()
        # 중복 제거 (제목 기준)
        existing_titles = {a.get("title") for a in articles_common}
        tool_fetched_unique = [a for a in tool_fetched if a.get("title") not in existing_titles]
        articles_common_final = articles_common + tool_fetched_unique

        return {
            "topic": topic,
            "rounds": all_rounds,
            "moderator": moderator_result,
            "articles": {
                "common": articles_common_final,
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
    for i, s in enumerate(steps):
        if s["role"] == target_role and s["action"] == target_action:
            return i
    return None


def _compute_levels(steps: list[dict]) -> list[list[int]]:
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
    return {
        "round":   round_num,
        "role":    step["role"],
        "kind":    step["action"],
        "content": result.get("content", ""),
        "tags":    result.get("tags", []),
    }
