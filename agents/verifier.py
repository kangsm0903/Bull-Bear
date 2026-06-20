"""
agents/verifier.py — 출력 수치의 데이터 근거 검증 (결정적/규칙 기반)

LLM 없이, 답변(content)에 등장한 금융 수치가 입력 데이터(source)에
실제로 존재하는지 문자열로 대조한다. 못 찾은 수치 목록을 돌려준다.

한계: 표현 차이(예: 59만원 ↔ 590,000원)로 오탐할 수 있고,
수치끼리의 정합성(예: 목표가·현재가로 계산한 상승여력)은 검증하지 못한다.
따라서 결과는 '확인 필요' 신호로만 쓰고, 최종 판단은 Self-Reflection(LLM)에 맡긴다.
"""

import re

# 숫자 + (선택) 금융 단위. 긴 단위가 먼저 매칭되도록 순서 유지(조원 > 조/원).
_UNITS = ["%p", "%", "％", "조원", "억원", "만원", "배", "포인트", "bp", "조", "억", "만", "원"]
_NUM = r"-?\d[\d,]*(?:\.\d+)?"
_TOKEN_RE = re.compile(rf"({_NUM})\s*({'|'.join(map(re.escape, _UNITS))})?")


def _is_meaningful(num: str, unit: str) -> bool:
    """금융적으로 의미 있는 수치만 검증 대상으로 (목록번호·연도 등 잡음 제외)."""
    if unit:
        return True
    # 단위가 없으면 콤마(자릿수)나 소수점이 있는 수치만 대상 (연도·한 자리 등 제외)
    return ("," in num) or ("." in num)


def extract_numbers(text: str) -> list[tuple[str, str]]:
    """(콤마 제거한 숫자, 단위) 튜플 리스트. 중복 제거, 등장 순서 보존."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for m in _TOKEN_RE.finditer(text):
        num, unit = m.group(1), (m.group(2) or "")
        if not _is_meaningful(num, unit):
            continue
        key = (num.replace(",", ""), unit)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def verify_numbers(content: str, source: str) -> list[str]:
    """content의 수치 중 source에서 못 찾은 것들을 표시용 문자열로 반환."""
    haystack = source.replace(",", "")
    ungrounded: list[str] = []
    for num, unit in extract_numbers(content):
        needle = f"{num}{unit}"
        if needle in haystack:
            continue
        # 단위 없는 숫자는 숫자만으로 대조 (단위가 있으면 단위까지 일치해야 함)
        if not unit and num in haystack:
            continue
        ungrounded.append(needle)
    return ungrounded
