"""
generate_results.py — 현재 시스템(앱과 동일 설정)으로 200종목 검색 결과 생성

실제 orchestrator와 같은 파라미터(감성 가중치 + 최신성 가중치)로 종목별
common/bull/bear 선택 기사를 results/retrieval_results_CURRENT.md 로 저장.

실행:
    python generate_results.py
"""

import sqlite3
from pathlib import Path

import rag.retriever as R
from agents.query_expander import expand_query
from agents.config import (TOP_K_COMMON, TOP_K_SIDE, RECENT_POOL,
                           SENTIMENT_WEIGHT, RECENCY_WEIGHT)

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "retrieval_results_CURRENT.md"

names = [r[0] for r in sqlite3.connect(BASE / "identifier.sqlite").execute(
    "SELECT corp_name FROM companies ORDER BY market_cap DESC LIMIT 200").fetchall()]

SPECS = [("common", "common", TOP_K_COMMON, None),
         ("bull",   "bull",   TOP_K_SIDE,   "bull"),
         ("bear",   "bear",   TOP_K_SIDE,   "bear")]

lines = ["# 검색 결과 — 현재 시스템 (LLM+ML 감성 · 최신성 가중치)\n",
         f"> 200종목 · 감성가중 {SENTIMENT_WEIGHT} · 최신성가중 {RECENCY_WEIGHT} · 풀 {RECENT_POOL}\n"]
bull_empty = bear_empty = 0

for i, name in enumerate(names, 1):
    t = R._detect_ticker(name)
    if not t:
        lines.append(f"\n## {name}  (감지 실패)\n")
        continue
    q = expand_query(name)
    lines.append(f"\n## {name}  ({t})\n")
    for tag, key, k, bias in SPECS:
        res = R.search(q[key], top_k=k, recent_pool=RECENT_POOL, bias=bias,
                       sentiment_weight=SENTIMENT_WEIGHT, recency_weight=RECENCY_WEIGHT)
        lines.append(f"**{tag}** ({len(res)}건)")
        if not res:
            lines.append("- (없음)")
        for a in res:
            s = R._get_sentiment(a)
            lines.append(f"- [{s:+.2f}] {a.get('published_at','')[:10]} · {a.get('title','')}")
        lines.append("")
        if tag == "bull" and not res:
            bull_empty += 1
        if tag == "bear" and not res:
            bear_empty += 1
    print(f"  {i}/200  {name}", end="\r")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"\n저장: {OUT}")
print(f"bull 빈 종목 {bull_empty}/200 | bear 빈 종목 {bear_empty}/200")
