# 신뢰성 점검 · 근거 비대칭 노출 — 설계/평가 문서

멀티에이전트 토론 시스템에서 "이 에이전트가 만든 답변을 믿어도 되는가"를 5개 축으로 점검하고,
현재 코드/실험이 각 축을 얼마나 충족하는지 정리한다. 마지막에 이번에 추가한 **근거 비대칭(data_balance) 노출**의 설계를 기록한다.

> 참고 문서: 실험 근거는 [EXPERIMENTS.md](../EXPERIMENTS.md), 환각 가드는 [tool-calling-and-persona.md](./tool-calling-and-persona.md) §4 참조.

---

## 1. 사실성(환각) — 강함, 일부 공백

**충족**
- **RAG grounding 강제**: argue/rebut 프롬프트가 "근거는 위 데이터에서만"을 명시(`agents/prompts.py`). No-RAG는 실험4에서 0/3 FAIL로 치명적임이 검증됨.
- **수치를 자유생성에 맡기지 않음**: 정량은 `rag/quant_fetcher.py`가 구조화 데이터로 뽑아 템플릿(`format_quant`)에 채우고, 출력 수치는 `agents/verifier.py`의 결정적 대조(`verify_numbers`)로 검증(`agents/analyst.py` `_reflect`). 노이즈 주입 실험(18)에서 가짜 수치 0/3 인용.
- **Self-Reflection 4기준**(할루시네이션·역할일관성·근거인용·논리비약) + temperature 0.4 + `RAG_MIN_SCORE` 하한.

**공백**
- **claim→source 매핑/citation이 구조적으로 강제되지 않음.** "근거 인용"은 프롬프트 권고일 뿐, 주장별 출처 ID를 강제하지 않아 *오귀속*(데이터엔 있으나 엉뚱한 맥락에 붙인 수치)은 잡지 못함.
- 이를 claim-evidence faithfulness judge로 잡으려다 **gpt-4o-mini 한계로 폐기**(전망·리스크 추론을 환각으로 과탐지, Bear 약화). 상세는 환각 가드 문서 §4.5.

## 2. 논증 품질(양극화/반박) — 실험으로 가장 깊게 검증

**충족**
- **병렬 독백 방지**: rebut은 실제 상대 발언(`opponent_statement`)을 주입하고 "상대 주장의 구체적 논점을 짚어 반박"을 강제(`prompts.py` `build_rebut_prompt`), 의존성 레벨로 실제 체이닝(`orchestrator._compute_levels`).
- **역할 swap 일관성 실측**: 대칭 데이터(17)·노이즈(18)에서 동일 데이터로도 role_consistency 9.0→9.67 상승 → "데이터 중계가 아닌 역할 기반 해석"(인사이트 2).
- **수렴 판정기**가 "표현만 바뀐 반복"을 차단(`build_convergence_prompt`).

**공백/리스크**
- **강제 양극화 리스크는 실재**: 종목 감성 편향(5) + R2 데이터 비대칭(23, 주원인 ~63%)으로 한쪽이 구조적으로 불리해도, 기존엔 그 비대칭이 결론에 드러나지 않았음. → **본 문서 §6에서 노출 추가.**
- role-swap 일관성 체크가 오프라인 실험에만 있고 라이브엔 없음.

## 3. 정량 평가(LLM-judge) — 인프라는 있으나 라이브 미노출

**충족**
- Moderator = 종합 judge, verdict 4단계 고정(`매수 적극|분할 매수|관망|매도 고려`).
- 평가 하베스트가 풍부: EXPERIMENTS.md 23개 ablation, judge 축이 logic / evidence_citation / role_consistency / rebuttal_directness.
- judge 캘리브레이션: judge 모델 비교(13) mini vs 4o(4o가 환각 1건 추가 탐지), rubric 피드백 루프(21)는 +0.5 향상 실증.

**공백**
- 품질 축들이 **오프라인 ablation에만 존재**하고, 프로덕션 Moderator는 summary+verdict만 출력(논리/인용/반박 점수는 라이브 미반영).

## 4. 안정성/재현성 — 프로젝트의 강점(전부 실측)

**충족**
- Self-Consistency(12): N=5에서 1회 FAIL이 평균을 끌어내림 → Best-of-3 최적 발견.
- Temperature(6): high→환각 실증 후 프로덕션 0.4로 인하.
- 민감도(18)·선공순서 무관(8)까지 측정.

**공백**
- **Best-of-N이 프로덕션에 없음**(argue 1회 생성). 실험12의 "5번 중 1번 FAIL"을 라이브 단일 실행은 그대로 맞을 수 있고 안전망이 없음.

## 5. 신뢰도의 사용자 노출 — 출처는 됨, 메타는 부족

**충족**
- 출처 사이드바: `articles{common, bull, bear}` 반환 + 메시지별 `researched_articles` 추적, 면책 고지 주입(`_inject_disclaimer`).

**공백**
- "결론이 N회 중 M회 동일" 안정성 지표 없음(프로덕션 다중실행 부재와 연결).
- 주장별 출처 링크(claim→article) 없음 — side 단위 기사 목록까지만.
- 근거 강도/방향성 메타가 UI에 없었음 → **본 문서 §6에서 1차 노출 추가.**

---

## 6. 추가 기능 — 근거 비대칭(data_balance) 노출 ✅

§2·§5의 공백을 메우는 1차 개선. 실험23이 정량화한 "데이터 비대칭"을 **사용자에게 한 줄로 투명하게 노출**한다.

### 설계 결정
- **무엇을**: 토론에서 인용된 근거(기사·정량 지표) **자체가 어느 쪽에 유리한지**를 1문장으로. 양측이 비슷하면 "균형".
- **무엇이 아닌가**: "누가 더 잘 논증했는가"가 아님. 논증 품질이 아니라 **입력 데이터의 방향성**이다. 따라서 verdict와 독립적이다(예: 정량은 Bear에 유리해도 종합 verdict는 분할 매수일 수 있음 — 사용자가 이 간극을 인지하게 하는 게 목적).
- **결정적 계산이 아닌 LLM 판정**: side별 기사 수는 hybrid 모드에서 `TOOL_MAX_ARTICLES_PER_SIDE`로 양측 상한이 같아 비대칭의 충실한 지표가 못 됨. 비대칭은 "데이터가 어느 입장을 더 뒷받침하느냐"는 판단이라, 전체 토론+기사를 보는 Moderator가 판정하는 것이 올바른 altitude.
- **개인화와 독립**: data_balance는 사실적 방향성이라 persona/horizon의 영향을 받지 않는다.

### 변경 파일
| 파일 | 변경 |
|------|------|
| `agents/prompts.py` | `build_moderator_prompt` 출력에 `data_balance` 필드 + 지시 추가 |
| `main.py` | API moderator 응답 화이트리스트에 `data_balance` 통과 |
| `frontend/src/app/components/DebateChat.tsx` | `Moderator` 인터페이스에 `data_balance` + verdict 배지 아래 "근거 균형 · …" 렌더 |
| `test_debate.py` | CLI 결론 출력에 "근거 균형:" 줄 추가 |

### 검증
- CLI end-to-end: `근거 균형: 정량 지표는 Bear 측에 유리, 기사 근거는 균형` 출력 확인. verdict(분할 매수)와 방향성이 분리돼 나옴.
- 프론트는 `data_balance`가 비어 있으면 렌더하지 않음(하위 호환).

---

## 7. 남은 개선 권고 (가성비 순)

1. **근거 비대칭 노출** — ✅ 완료(§6).
2. **수렴/결론 라운드만 Best-of-3** — 실험12가 최적이라 못 박은 값. 최종 결론에만 적용하면 비용 통제 + "단일 나쁜 샘플" 리스크 제거 + N회 일치 지표(§5 공백)까지 자연히 노출.
3. **생성기를 gpt-4o로 격상** — claim→source 인용 강제는 mini로는 무리(faithfulness judge 폐기에서 확인). 근본 해법은 판정기 추가가 아니라 생성기 격상(실험1·16: 4o만 유의미하게 높음). 비용 결정 영역.
