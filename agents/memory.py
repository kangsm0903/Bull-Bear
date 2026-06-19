"""
agents/memory.py — 토론 결과 메모리 저장/검색

과거 토론 결과를 JSON 파일로 저장하고,
새 토론 시작 시 관련 과거 토론을 검색하여 에이전트 컨텍스트로 주입합니다.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.config import ENABLE_MEMORY, MAX_MEMORY_REFS, MEMORY_DIR


class DebateMemory:

    def __init__(self):
        self.path = Path(MEMORY_DIR)
        self.path.mkdir(exist_ok=True)

    def save(self, topic: str, ticker: str, moderator_result: dict) -> None:
        """토론 결과를 메모리 파일로 저장."""
        if not ENABLE_MEMORY:
            return
        entry = {
            "topic":        topic,
            "ticker":       ticker or "",
            "date":         datetime.now().strftime("%Y-%m-%d"),
            "verdict":      moderator_result.get("verdict", ""),
            "bull_summary": moderator_result.get("bull_summary", ""),
            "bear_summary": moderator_result.get("bear_summary", ""),
        }
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{ticker or topic}.json"
        (self.path / fname).write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [Memory] 저장 완료: {fname}")

    def search(self, ticker: str, topic: str) -> list[dict]:
        """ticker(우선) 또는 topic 기준으로 최신 MAX_MEMORY_REFS개 반환."""
        if not ENABLE_MEMORY:
            return []
        files = sorted(self.path.glob("*.json"), reverse=True)
        results = []
        for f in files:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if ticker and d.get("ticker") == ticker:
                    results.append(d)
                elif not ticker and d.get("topic") == topic:
                    results.append(d)
                if len(results) >= MAX_MEMORY_REFS:
                    break
            except Exception:
                continue
        return results

    def format(self, memories: list[dict]) -> str:
        """메모리 목록을 프롬프트용 텍스트로 변환."""
        if not memories:
            return ""
        lines = []
        for m in memories:
            lines.append(
                f"[{m['date']}] {m['topic']} — 판정: {m['verdict']}\n"
                f"  Bull 요약: {m['bull_summary']}\n"
                f"  Bear 요약: {m['bear_summary']}"
            )
        return "\n\n".join(lines)
