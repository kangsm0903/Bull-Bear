"""
compare_research_modes.py — per_step vs upfront 리서치 모드 비교 실험

실행:
  python compare_research_modes.py per_step
  python compare_research_modes.py upfront

모드를 import 전에 config에 주입해야 prompts/analyst/orchestrator가
올바른 RESEARCH_MODE 값을 읽는다. (각 모듈이 import 시점에 값을 바인딩하기 때문)
"""
import os
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "per_step"
topic = sys.argv[2] if len(sys.argv) > 2 else "삼성전자"

# agents 패키지 import 전에 env로 모드 주입 (config가 os.getenv로 읽음).
# (agents/__init__.py가 orchestrator를 끌어오므로 import 후 덮어쓰면 늦음)
os.environ["RESEARCH_MODE"] = mode

from agents.orchestrator import DebateOrchestrator  # noqa: E402
import agents.analyst as _a  # noqa: E402
assert _a.RESEARCH_MODE == mode, f"모드 주입 실패: {_a.RESEARCH_MODE} != {mode}"


def _overlap(a: list[dict], b: list[dict]) -> int:
    def keys(xs):
        return {x.get("url") or x.get("title") for x in xs}
    return len(keys(a) & keys(b))


def main():
    print(f"\n{'='*60}\n  RESEARCH_MODE = {mode} | topic = {topic}\n{'='*60}")
    orch = DebateOrchestrator()

    t0 = time.time()
    result = orch.run(topic=topic)
    elapsed = time.time() - t0

    rounds = result["rounds"]
    bull_arts = result["articles"]["bull"]
    bear_arts = result["articles"]["bear"]
    n_msgs = sum(len(r) for r in rounds)

    print(f"\n{'─'*60}\n  지표 요약 ({mode})\n{'─'*60}")
    print(f"  소요 시간      : {elapsed:.1f}s")
    print(f"  라운드 수      : {len(rounds)}")
    print(f"  총 발언 수     : {n_msgs}")
    print(f"  Bull 조사 기사 : {len(bull_arts)}건")
    print(f"  Bear 조사 기사 : {len(bear_arts)}건")
    print(f"  기사 중복      : {_overlap(bull_arts, bear_arts)}건 (낮을수록 차별화↑)")
    print(f"  최종 판단      : {result['moderator'].get('verdict','')}")


if __name__ == "__main__":
    main()
