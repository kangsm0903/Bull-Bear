"""
삼성전자 토론 테스트 스크립트
실행: python test_debate.py
"""
import json
from agents.orchestrator import DebateOrchestrator

def main():
    topic = "삼성전자"
    print(f"\n{'='*60}")
    print(f"  토론 주제: {topic}")
    print(f"{'='*60}\n")

    orchestrator = DebateOrchestrator()

    def on_round_complete(round_num, bull_result, bear_result):
        print(f"\n{'─'*50}")
        print(f"  Round {round_num}")
        print(f"{'─'*50}")
        print(f"\n🐂 [Bull]")
        print(f"  {bull_result.get('content', '')}")
        print(f"  태그: {bull_result.get('tags', [])}")

        print(f"\n🐻 [Bear]")
        print(f"  {bear_result.get('content', '')}")
        print(f"  태그: {bear_result.get('tags', [])}")

    result = orchestrator.run(
        topic=topic,
        on_round_complete=on_round_complete,
    )

    # Moderator 결론 출력
    mod = result["moderator"]
    print(f"\n{'='*60}")
    print(f"  ⚖️  Moderator 최종 결론")
    print(f"{'='*60}")
    print(f"\n📈 Bull 요약: {mod.get('bull_summary', '')}")
    print(f"\n📉 Bear 요약: {mod.get('bear_summary', '')}")
    print(f"\n💡 종합 의견: {mod.get('conclusion', '')}")
    print(f"\n🏁 투자 판단: {mod.get('verdict', '')}")

    # 사용된 기사 출력
    print(f"\n{'─'*50}")
    print(f"  📰 사용된 기사 (공통 {len(result['articles']['common'])}건)")
    print(f"{'─'*50}")
    for a in result["articles"]["common"]:
        print(f"  - [{a.get('ticker','')}] {a.get('title','')[:50]}...")

if __name__ == "__main__":
    main()
