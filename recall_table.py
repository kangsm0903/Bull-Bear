"""3방식의 3분류 정확도 + 호재/악재/중립 재현율 (각자 최적 기준선, gpt-5.4 정답 500건)."""
import json
import sqlite3

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

import experiment_sentiment_3way as E
from train_sentiment_model import BODY_CHARS
from rag.sentiment import sentiment_score

sample = E.fetch_strata()
truth = json.loads(E.CACHE.read_text())
ids = [a["id"] for a in sample if a["id"] in truth]
y = np.array([truth[i] for i in ids])
amap = {a["id"]: a for a in sample}

def txt(t, c): return f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip()
def disc(s):   return 1 if s > 0.05 else (-1 if s < -0.05 else 0)

print("점수 계산...")
dict_s = np.array([sentiment_score(amap[i]["title"], amap[i]["content"]) for i in ids])
llm_s = np.array([float(amap[i]["llm"]) for i in ids])

# ML-v3 test 격리 재학습
rows = sqlite3.connect(E.DB).execute(
    "SELECT id, title, content, sentiment FROM articles WHERE sentiment IS NOT NULL").fetchall()
tid = {a["id"] for a in sample}
tr = [(txt(t, c), disc(s)) for i, t, c, s in rows if i not in tid]
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=3,
                      max_features=50000).fit([x[0] for x in tr])
clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(
    vec.transform([x[0] for x in tr]), np.array([x[1] for x in tr]))
cl = list(clf.classes_); ip, ineg = cl.index(1), cl.index(-1)
srow = {i: (t, c) for i, t, c, s in rows}
proba = clf.predict_proba(vec.transform([txt(*srow[i]) for i in ids]))
v3_s = proba[:, ip] - proba[:, ineg]

def best_band(s):
    return max(np.arange(0, 0.51, 0.02), key=lambda b: (np.where(s > b, 1, np.where(s < -b, -1, 0)) == y).mean())

def metrics(s):
    b = best_band(s)
    p = np.where(s > b, 1, np.where(s < -b, -1, 0))
    acc3 = (p == y).mean() * 100
    rec = {c: (p[y == c] == c).mean() * 100 for c in (1, -1, 0)}
    return b, acc3, rec[1], rec[-1], rec[0]

print(f"\ngpt-5.4 정답 분포: 호재 {(y==1).sum()} / 악재 {(y==-1).sum()} / 중립 {(y==0).sum()}\n")
print(f"{'방식':14s} {'최적band':>8s} {'3분류':>7s} {'호재재현':>8s} {'악재재현':>8s} {'중립재현':>8s}")
for name, s in [("단어사전", dict_s), ("4o-mini", llm_s), ("ML-v3", v3_s)]:
    b, a, pr, nr, zr = metrics(s)
    print(f"{name:14s} {b:8.2f} {a:6.1f}% {pr:7.1f}% {nr:7.1f}% {zr:7.1f}%")
