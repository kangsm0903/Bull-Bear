"""
fair_bandsweep.py — 4방식 공정 비교: 같은 기준선(band)으로 3분류 정확도 비교

각 방식의 연속 점수에 동일 기준선을 적용해 호재/악재/중립 판정 → gpt-5.4 정답과 채점.
band을 0~0.4로 쓸며, ① 동일 기준선 비교 + ② 각자 최적 기준선을 표로.
(ML-v3는 분류기라 argmax 결과도 별도 표기)
실행:  python fair_bandsweep.py
"""
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
BANDS = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40]

def txt(t, c): return f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip()
def disc(s):   return 1 if s > 0.05 else (-1 if s < -0.05 else 0)

print("■ 1) 단어사전 점수")
dict_s = np.array([sentiment_score(amap[i]["title"], amap[i]["content"]) for i in ids])
print("■ 2) 4o-mini 저장 점수")
llm_s = np.array([float(amap[i]["llm"]) for i in ids])
print("■ 3) ML-v1 (회귀, test 격리) 학습/예측")
v1d = E.ml_predict_isolated(sample)
v1_s = np.array([v1d[i] for i in ids])

print("■ 4) ML-v3 (분류기, test 격리) 학습/예측")
rows = sqlite3.connect(E.DB).execute(
    "SELECT id, title, content, sentiment FROM articles WHERE sentiment IS NOT NULL").fetchall()
test_ids = {a["id"] for a in sample}
tr = [(txt(t, c), disc(s)) for i, t, c, s in rows if i not in test_ids]
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                      min_df=3, max_features=50000).fit([x[0] for x in tr])
clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(
    vec.transform([x[0] for x in tr]), np.array([x[1] for x in tr]))
cl = list(clf.classes_); ip, ineg = cl.index(1), cl.index(-1)
srow = {i: (t, c) for i, t, c, s in rows}
Xte = vec.transform([txt(*srow[i]) for i in ids])
proba = clf.predict_proba(Xte)
v3_s = proba[:, ip] - proba[:, ineg]            # 연속 점수(부호·band용)
v3_argmax = clf.predict(Xte)                     # 직접 3분류

methods = [("단어사전", dict_s), ("4o-mini", llm_s),
           ("ML-v1 회귀", v1_s), ("ML-v3 분류기", v3_s)]

def acc3_at(s, band):
    p = np.where(s > band, 1, np.where(s < -band, -1, 0))
    return (p == y).mean() * 100

print("\n■ ① 동일 기준선에서 3분류 정확도 (정답=gpt-5.4, {}건)".format(len(ids)))
hdr = "    {:14s}".format("방식") + "".join(f"±{b:.2f} " for b in BANDS)
print(hdr)
for name, s in methods:
    line = "    {:14s}".format(name) + "".join(f"{acc3_at(s, b):5.1f} " for b in BANDS)
    print(line)
print(f"    {'ML-v3 argmax':14s}" + f"{(v3_argmax==y).mean()*100:5.1f} (직접 분류, band 무관)")

print("\n■ ② 각 방식의 '최적 기준선'에서의 3분류")
print("    {:14s} {:>10s} {:>10s}".format("방식", "최적band", "3분류"))
for name, s in methods:
    accs = [(b, acc3_at(s, b)) for b in np.arange(0, 0.51, 0.02)]
    bb, ba = max(accs, key=lambda x: x[1])
    print(f"    {name:14s} {bb:10.2f} {ba:9.1f}%")

print("\n■ 부호 정확도 (방향, band 무관 — 정답 호재/악재만)")
nz = y != 0
for name, s in methods:
    print(f"    {name:14s} {(np.sign(s)[nz]==y[nz]).mean()*100:5.1f}%")
