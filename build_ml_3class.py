"""
build_ml_3class.py — ML v3: 3분류 분류기 (회귀 → 로지스틱 3-class)

목표: ML을 4o-mini 분류 수준(특히 3분류 65%)까지. ML은 4o-mini 증류라 충실히
베끼면 4o-mini에 수렴해야 하는데, 회귀+좁은띠 탓에 '중립'을 못 베낌 → 분류기로 교체.

  · 입력: 글자조각 TF-IDF (v1과 동일, 임베딩보다 나았음)
  · 정답: 4o-mini 라벨을 3-class로 이산화 (호재>0.05 / 악재<-0.05 / 중립)
  · 모델: LogisticRegression(multinomial, class_weight=balanced)
  · 출력: 클래스(3분류용) + 연속점수 P(호재)-P(악재)(부호·랭킹용)
평가: 같은 500건(test 격리) · gpt-5.4 정답지. v1/4o-mini와 비교.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

import experiment_sentiment_3way as E
from train_sentiment_model import BODY_CHARS

BASE = Path(__file__).resolve().parent
DB = BASE / "identifier.sqlite"
T = 0.05   # 4o-mini 라벨 이산화 임계 (중립 경계)

rows = sqlite3.connect(DB).execute(
    "SELECT id, title, content, sentiment FROM articles WHERE sentiment IS NOT NULL"
).fetchall()
sample = E.fetch_strata()
test_ids = {a["id"] for a in sample}
truth = json.loads(E.CACHE.read_text())

def txt(t, c): return f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip()
def disc(s):   return 1 if s > T else (-1 if s < -T else 0)

tr = [(txt(t, c), disc(s)) for i, t, c, s in rows if i not in test_ids]
Xtr_txt = [x[0] for x in tr]
ytr = np.array([x[1] for x in tr])
print(f"■ 학습 {len(tr)}건 — 4o-mini 3분류 분포: "
      f"호재 {int((ytr==1).sum())} / 악재 {int((ytr==-1).sum())} / 중립 {int((ytr==0).sum())}")

vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                      min_df=3, max_features=50000).fit(Xtr_txt)
clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0)
clf.fit(vec.transform(Xtr_txt), ytr)
classes = list(clf.classes_)            # 예: [-1, 0, 1]
ip, ineg = classes.index(1), classes.index(-1)

sample_rows = {i: (t, c) for i, t, c, s in rows}
ids = [a["id"] for a in sample if a["id"] in truth and a["id"] in sample_rows]
Xte = vec.transform([txt(*sample_rows[i]) for i in ids])
proba = clf.predict_proba(Xte)
pred_cls = clf.predict(Xte)                                  # 3분류 직접
score = proba[:, ip] - proba[:, ineg]                       # 연속점수(부호·랭킹)

y = np.array([truth[i] for i in ids])
name = {1: "호재", -1: "악재", 0: "중립"}

acc3 = (pred_cls == y).mean()*100
nz = y != 0
sign = (np.sign(score)[nz] == y[nz]).mean()*100
pos_rec = (pred_cls[y == 1] == 1).mean()*100
neg_rec = (pred_cls[y == -1] == -1).mean()*100

print(f"\n■ ML v3 (3분류 분류기) — 정답=gpt-5.4 {len(ids)}건")
print(f"    3분류 {acc3:.1f}% | 부호 {sign:.1f}% | 호재재현 {pos_rec:.1f}% | 악재재현 {neg_rec:.1f}%")
print("    " + "-"*60)
print("    [v1 회귀]    3분류 44.6% | 부호 84.7% | 호재 81.3% | 악재 81.6%")
print("    [4o-mini]    3분류 65.4% | 부호 79.0% | 호재 70.7% | 악재 91.8%  ← 목표")

print("\n■ 혼동행렬 v3 (행=gpt-5.4 정답)")
print("    정답＼예측   호재  악재  중립")
for a in [1, -1, 0]:
    r = [int(((y == a) & (pred_cls == b)).sum()) for b in [1, -1, 0]]
    print(f"    {name[a]:>6s}     {r[0]:4d} {r[1]:4d} {r[2]:4d}")
