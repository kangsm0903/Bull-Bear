"""
FAISS 기사 검색만 테스트 (GPT 호출 없음).

orchestrator가 토론 전에 수행하는 '데이터 준비' 단계만 떼어내 확인합니다.
임베딩·FAISS·SQLite 조회까지만 돌리고, LLM은 호출하지 않습니다.

실행:
    python test_retrieval.py                # 기본: 삼성전자
    python test_retrieval.py SK하이닉스      # 종목 지정
    python test_retrieval.py SK하이닉스 50   # recent_pool 크기 지정
"""

import sys

from agents.query_expander import expand_query
from agents.config import TOP_K_COMMON, TOP_K_SIDE, RECENT_POOL
from rag.retriever import search, _detect_ticker, _ticker_to_name


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    pool  = int(sys.argv[2]) if len(sys.argv) > 2 else RECENT_POOL

    print(f"■ 주제: {topic}")
    ticker = _detect_ticker(topic)
    print(f"■ 감지 ticker: {ticker} ({_ticker_to_name(ticker) if ticker else '미감지'})")
    print(f"■ recent_pool: {pool}")

    queries = expand_query(topic)
    print("■ 확장 쿼리:")
    for k, v in queries.items():
        print(f"    {k:>7}: {v}")

    sets: dict[str, list[dict]] = {}
    for label, q, k in [
        ("common", queries["common"], TOP_K_COMMON),
        ("bull",   queries["bull"],   TOP_K_SIDE),
        ("bear",   queries["bear"],   TOP_K_SIDE),
    ]:
        print(f"\n=== {label}  (top_k={k})  [개별 검색 결과 — 중복 가능] ===")
        results = search(q, source="articles", top_k=k, recent_pool=pool)
        sets[label] = results
        if not results:
            print("    (결과 없음)")
        for a in results:
            print(f"    [{a['score']:.3f}] {a.get('published_at','')[:10]} "
                  f"| {a.get('title','')[:55]}")

    # ── 앱과 동일한 최종(중복 제거) 뷰 ──────────────────────
    # main.py의 dedup 로직과 동일: common 포함 또는 bull+bear 양쪽 → both
    seen: dict = {}
    for side in ("common", "bull", "bear"):
        for a in sets[side]:
            key = a.get("faiss_id") or a.get("url") or a.get("title")
            seen.setdefault(key, {"a": a, "sides": set()})["sides"].add(side)

    print(f"\n=== 최종 (중복 제거 — 앱 사이드바와 동일) : {len(seen)}개 ===")
    counts = {"both": 0, "bull": 0, "bear": 0}
    for e in seen.values():
        sides = e["sides"]
        if "common" in sides or ("bull" in sides and "bear" in sides):
            ref = "both"
        elif "bull" in sides:
            ref = "bull"
        else:
            ref = "bear"
        counts[ref] += 1
        print(f"    [{ref:>4}] {e['a'].get('published_at','')[:10]} "
              f"| {e['a'].get('title','')[:55]}")
    print(f"\n  Bull 전용 {counts['bull']} | Shared(both) {counts['both']} | Bear 전용 {counts['bear']}")


if __name__ == "__main__":
    main()
