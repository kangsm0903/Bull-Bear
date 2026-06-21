"""
토론 테스트 스크립트
실행: python test_debate.py [주제] [페르소나]
  예) python test_debate.py 삼성전자 입문자
  페르소나: 입문자 | 개인투자자 | 전문가 (생략 시 중립)
"""
import sys
from agents.orchestrator import DebateOrchestrator

def main():
    topic   = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    persona = sys.argv[2] if len(sys.argv) > 2 else ""
    print(f"\n{'='*60}")
    print(f"  토론 주제: {topic}" + (f" | 독자: {persona}" if persona else ""))
    print(f"{'='*60}\n")

    orchestrator = DebateOrchestrator()

    def on_round_complete(round_num, round_msgs):
        print(f"\n{'─'*50}")
        print(f"  Round {round_num}")
        print(f"{'─'*50}")
        for msg in round_msgs:
            role_label = "[Bull]" if msg["role"] == "bull" else "[Bear]"
            kind = msg.get("kind", "")
            print(f"\n{role_label} ({kind})")
            print(f"  {msg.get('content', '')}")
            print(f"  tags: {msg.get('tags', [])}")

    result = orchestrator.run(
        topic=topic,
        on_round_complete=on_round_complete,
        user_persona=persona,
    )

    # Moderator 결론 출력
    mod = result["moderator"]
    print(f"\n{'='*60}")
    print(f"  [Moderator] 최종 결론")
    print(f"{'='*60}")
    print(f"\nBull 요약: {mod.get('bull_summary', '')}")
    print(f"\nBear 요약: {mod.get('bear_summary', '')}")
    print(f"\n종합 의견: {mod.get('conclusion', '')}")
    print(f"\n투자 판단: {mod.get('verdict', '')}")
    if mod.get("data_balance"):
        print(f"\n근거 균형: {mod.get('data_balance', '')}")

    # 사용된 기사 출력
    print(f"\n{'─'*50}")
    print(f"  사용된 기사 (공통 {len(result['articles']['common'])}건)")
    print(f"{'─'*50}")
    for a in result["articles"]["common"]:
        print(f"  - [{a.get('ticker','')}] {a.get('title','')[:50]}...")

if __name__ == "__main__":
    main()
