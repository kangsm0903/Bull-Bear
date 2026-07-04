"""
generate_results_v3.py — ML-v3(3분류 분류기) 감성으로 200종목 기사 선정 결과 생성

v3 분류기를 전체 라벨로 학습 → 모든 기사에 v3 점수(P호재-P악재) 부여 →
retriever의 감성만 v3로 교체(monkeypatch)하고 동일 파이프라인으로 200종목 검색.
산출: results/retrieval_results_ML_V3.md
"""
import sqlite3
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

import rag.retriever as R
from agents.query_expander import expand_query
from agents.config import (TOP_K_COMMON, TOP_K_SIDE, RECENT_POOL,
                           SENTIMENT_WEIGHT, RECENCY_WEIGHT)
from train_sentiment_model import BODY_CHARS

BASE = Path(__file__).resolve().parent
DB = BASE / "identifier.sqlite"
OUT = BASE / "results" / "retrieval_results_ML_V3.md"
T = 0.05

def txt(t, c): return f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip()
def disc(s):   return 1 if s > T else (-1 if s < -T else 0)

print("■ v3 분류기 학습 (전체 라벨)...")
rows = sqlite3.connect(DB).execute(
    "SELECT title, content, sentiment FROM articles WHERE sentiment IS NOT NULL").fetchall()
Xtxt = [txt(t, c) for t, c, _ in rows]
ycls = np.array([disc(s) for _, _, s in rows])
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                      min_df=3, max_features=50000).fit(Xtxt)
clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(vec.transform(Xtxt), ycls)
cl = list(clf.classes_); ip, ineg = cl.index(1), cl.index(-1)

import joblib
joblib.dump({"vec": vec, "clf": clf}, BASE / "rag" / "sentiment_model_v3.joblib")
print("  저장: rag/sentiment_model_v3.joblib (재학습 불필요)")

print("■ 모든 기사에 v3 점수 부여...")
allrows = sqlite3.connect(DB).execute(
    "SELECT faiss_id, title, content FROM articles "
    "WHERE faiss_id IS NOT NULL AND title IS NOT NULL").fetchall()
proba = clf.predict_proba(vec.transform([txt(t, c) for _, t, c in allrows]))
v3map = {fid: float(proba[k, ip] - proba[k, ineg]) for k, (fid, _, _) in enumerate(allrows)}
print(f"  v3 점수: {len(v3map):,}건")

R._get_sentiment = lambda a: v3map.get(a.get("faiss_id"), 0.0)   # 감성만 v3로 교체

names = [r[0] for r in sqlite3.connect(DB).execute(
    "SELECT corp_name FROM companies ORDER BY market_cap DESC LIMIT 200")]
SPECS = [("common", "common", TOP_K_COMMON, None),
         ("bull", "bull", TOP_K_SIDE, "bull"),
         ("bear", "bear", TOP_K_SIDE, "bear")]

lines = ["# 기사 선정 결과 — ML-v3 (3분류 분류기) 감성\n",
         f"> 200종목 · 감성=v3(P호재-P악재) · 감성가중 {SENTIMENT_WEIGHT} · 최신성 {RECENCY_WEIGHT}\n"]
bull_e = bear_e = 0
for i, name in enumerate(names, 1):
    t = R._detect_ticker(name)
    if not t:
        lines.append(f"\n## {name}  (감지 실패)\n"); continue
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
        if tag == "bull" and not res: bull_e += 1
        if tag == "bear" and not res: bear_e += 1
    print(f"  {i}/200 {name}", end="\r")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"\n저장: {OUT}")
print(f"bull 빈 종목 {bull_e}/200 | bear 빈 종목 {bear_e}/200")
