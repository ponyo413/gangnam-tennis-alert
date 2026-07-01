# src/olympic.py
"""올림픽공원 테니스 레슨 '대기 현황표' 감시 — 로그인 없는 HTML 파싱(전용 부품).

강남·esongpa·대치유수지가 '코트 빈자리(취소표)'를 다루는 것과 달리, 여기서는
'레슨 대기 칸의 값 변화'를 본다. 칸 값 3종: 숫자(대기 가능·그 수)·'마감'(대기 마감)·'X'(레슨 없음).
값이 바뀌면(마감→숫자·숫자→숫자·숫자→마감) 알림, 마감↔X만 조용.
날짜 축이 없는 고정 주간표(주중/주말)라 '칸별 현재값 dict'만 다룬다.
"""


def _is_number(value):
    """값이 숫자(대기 가능)인지. None·'마감'·'X'는 False (None-안전)."""
    return str(value).strip().isdigit()


def classify_change(prev, cur):
    """칸 하나의 직전값(prev)→현재값(cur)으로 알림 종류를 정한다(순수함수).

    반환: '열림' / '변동' / '닫힘' / None(조용).
    - 값이 같으면 None.
    - 현재가 숫자면: 직전이 숫자 아님(마감/X/None) → '열림', 직전도 숫자(값 다름) → '변동'.
    - 현재가 숫자 아니면(마감/X): 직전이 숫자 → '닫힘', 아니면 None(마감↔X는 조용).
    """
    if prev == cur:
        return None
    if _is_number(cur):
        return "변동" if _is_number(prev) else "열림"
    return "닫힘" if _is_number(prev) else None
