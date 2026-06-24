# src/daechi.py
"""대치유수지 테니스장 빈자리 조회 — 로그인 없는 HTML 파싱(전용 부품).

강남(REST)·esongpa(로그인)와 사이트 방식이 달라 따로 둔다.
빈자리(possible_icn_on) 칸의 data-date/data-time과 <dt> 순서(A·B·C)로 슬롯을 만든다.
시간대/켜고끄기는 settings.yaml(설정표)에서 받아 is_wanted_for로 거른다.
"""
import re

from src.models import Slot

CENTER = "대치유수지"             # Slot.court(시설명)에 들어갈 이름
COURTS = ["A코트", "B코트", "C코트"]  # 한 행 <dt> 순서 = 코트 순서

# 한 시간대 행(<dl>) → 그 안의 코트 칸(<dt>) → 빈자리 단서(data-date/time + on)
_ROW_RE = re.compile(r"<dl>(.*?)</dl>", re.DOTALL)
_CELL_RE = re.compile(r"<dt>(.*?)</dt>", re.DOTALL)
_DATE_RE = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})"')
_TIME_RE = re.compile(r'data-time="(\d+)"')


def parse_daechi(html):
    """HTML에서 '가능'(빈자리) 칸만 Slot 목록으로.

    각 <dl>(한 시간대 행)의 <dt> 1·2·3번째를 A·B·C 코트로 본다.
    'possible_icn_on'이면서 data-date/data-time이 있는 칸만 빈자리로 뽑는다.
    시작시각 = 7 + data-time*2 (0→07시 … 6→19시).
    """
    slots = []
    for row in _ROW_RE.findall(html):
        for idx, cell in enumerate(_CELL_RE.findall(row)[:3]):  # 1·2·3 = A·B·C
            if "possible_icn_on" not in cell:
                continue  # 불가능(찬) 칸 → 건너뜀
            dm, tm = _DATE_RE.search(cell), _TIME_RE.search(cell)
            if not (dm and tm):
                continue  # 날짜/시간 꼬리표 없으면 빈자리로 안 봄(안전)
            hour = 7 + int(tm.group(1)) * 2
            slots.append(Slot(CENTER, COURTS[idx], dm.group(1), f"{hour:02d}:00"))
    return slots
