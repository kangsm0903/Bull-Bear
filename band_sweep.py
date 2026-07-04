"""중립 띠(band) 폭에 따라 ML의 중립 판정·3분류 정확도가 어떻게 변하는지 확인."""
import json
import numpy as np
import experiment_sentiment_3way as E

sample = E.fetch_strata()
truth = json.loads(E.CACHE.read_text())           # gpt-5.4 정답 (캐시)
ml = E.ml_predict_isolated(sample)                # test 격리 ML 예측

ids = [a["id"] for a in sample if a["id"] in truth]
y = np.array([truth[i] for i in ids])
s = np.array([ml[i] for i in ids])

print(f"\n■ ML 점수 분포 (500건 중 {len(ids)}건)")
for lo, hi, lbl in [(-1.01,-0.5,"강한악재 ≤-0.5"),(-0.5,-0.2,"-0.5~-0.2"),
                    (-0.2,-0.05,"-0.2~-0.05"),(-0.05,0.05,"중립권 ±0.05"),
                    (0.05,0.2,"0.05~0.2"),(0.2,0.5,"0.2~0.5"),(0.5,1.01,"강한호재 ≥0.5")]:
    print(f"    {lbl:14s}: {int(((s>=lo)&(s<hi)).sum()):4d}건")

print("\n■ 중립 띠(band)를 넓히면 — 3분류 정확도 변화 (정답=gpt-5.4)")
print("    band     중립예측  호재예측  악재예측 | 3분류정확도  부호정확도")
for band in [0.05, 0.10, 0.20, 0.30, 0.40]:
    p = np.where(s > band, 1, np.where(s < -band, -1, 0))
    acc3 = (p == y).mean()*100
    nz = y != 0
    sign = (np.sign(s[nz]) == y[nz]).mean()*100     # 부호는 band 무관(방향만)
    print(f"    ±{band:.2f}   {int((p==0).sum()):6d}  {int((p==1).sum()):7d}  "
          f"{int((p==-1).sum()):7d} | {acc3:8.1f}%  {sign:9.1f}%")
