"""
compare_sentiment_versions.py — 감성 버전 A/B 비교 결과 생성

같은 검색 코드를 감성 점수 산출 방식만 바꿔 200종목 검색 결과를 각각 파일로 저장.
  · OLD: 단어 사전(rag.sentiment.sentiment_score)만 사용
  · NEW: LLM 라벨(articles.sentiment) 우선, 없으면 단어 사전 폴백 (현행 _get_sentiment)

산출물 (results/):
  · retrieval_results_OLD.md  — 단어사전 버전, 종목별 common/bull/bear 기사
  · retrieval_results_NEW.md  — LLM 버전, 종목별 common/bull/bear 기사
콘솔에 두 버전의 bull/bear 빈 종목 수 통계 출력 (분석 md 작성용).
"""

import sqlite3
from pathlib import Path

import rag.retriever as R
from rag.sentiment import sentiment_score
from agents.query_expander import expand_query
from agents.config import TOP_K_COMMON, TOP_K_SIDE, RECENT_POOL, SENTIMENT_WEIGHT

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "results"
OUT_DIR.mkdir(exist_ok=True)

names = [r[0] for r in sqlite3.connect(BASE / "identifier.sqlite").execute(
    "SELECT corp_name FROM companies ORDER BY market_cap DESC LIMIT 200").fetchall()]

_orig_get_sentiment = R._get_sentiment
_dict_only = lambda a: sentiment_score(a.get("title"), a.get("content"))

SPECS = [("common", "common", TOP_K_COMMON, None),
         ("bull",   "bull",   TOP_K_SIDE,   "bull"),
         ("bear",   "bear",   TOP_K_SIDE,   "bear")]


def run_version(version: str) -> dict:
    """version="OLD"(단어사전) | "NEW"(LLM). 결과 md 문자열 + 통계 반환."""
    R._get_sentiment = _dict_only if version == "OLD" else _orig_get_sentiment

    lines = [f"# 검색 결과 — {version} "
             f"({'단어사전' if version=='OLD' else 'LLM 감성 라벨'})\n",
             f"> 200종목 · 종목별 common/bull/bear 선택 기사\n"]
    stat = {"bull_empty": 0, "bear_empty": 0}

    for name in names:
        t = R._detect_ticker(name)
        if not t:
            lines.append(f"\n## {name}  (감지 실패)\n")
            continue
        q = expand_query(name)
        lines.append(f"\n## {name}  ({t})\n")
        for tag, key, k, bias in SPECS:
            res = R.search(q[key], top_k=k, recent_pool=RECENT_POOL,
                           bias=bias, sentiment_weight=SENTIMENT_WEIGHT)
            lines.append(f"**{tag}** ({len(res)}건)")
            if not res:
                lines.append("- (없음)")
            for a in res:
                s = R._get_sentiment(a)
                lines.append(f"- [{s:+.2f}] {a.get('published_at','')[:10]} · {a.get('title','')}")
            lines.append("")
            if tag == "bull" and not res:
                stat["bull_empty"] += 1
            if tag == "bear" and not res:
                stat["bear_empty"] += 1

    return {"md": "\n".join(lines), "stat": stat}


print("OLD(단어사전) 생성 중...")
old = run_version("OLD")
(OUT_DIR / "retrieval_results_OLD.md").write_text(old["md"], encoding="utf-8")

print("NEW(LLM) 생성 중...")
new = run_version("NEW")
(OUT_DIR / "retrieval_results_NEW.md").write_text(new["md"], encoding="utf-8")

R._get_sentiment = _orig_get_sentiment  # 원복

print("\n═══ 통계 (분석 md 작성용) ═══")
print(f"  OLD(단어사전) | bull 빈 {old['stat']['bull_empty']}/200 | bear 빈 {old['stat']['bear_empty']}/200")
print(f"  NEW(LLM)      | bull 빈 {new['stat']['bull_empty']}/200 | bear 빈 {new['stat']['bear_empty']}/200")
print(f"\n저장: {OUT_DIR}/retrieval_results_OLD.md , retrieval_results_NEW.md")
