# src/daechi.py
"""대치유수지 테니스장 빈자리 조회 — 로그인 없는 HTML 파싱(전용 부품).

강남(REST)·esongpa(로그인)와 사이트 방식이 달라 따로 둔다.
빈자리(possible_icn_on) 칸의 data-date/data-time과 <dt> 순서(A·B·C)로 슬롯을 만든다.
시간대/켜고끄기는 settings.yaml(설정표)에서 받아 is_wanted_for로 거른다.
"""
import re
from datetime import datetime, timezone, timedelta

from src.filters import is_wanted_for
from src.http_session import make_session
from src.models import Slot

CENTER = "대치유수지"             # Slot.court(시설명)에 들어갈 이름
COURTS = ["A코트", "B코트", "C코트"]  # 한 행 <dt> 순서 = 코트 순서

KST = timezone(timedelta(hours=9))   # GitHub Actions는 UTC라 한국시각 고정
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
BASE = "https://www.xn--vk1b79znxd34c61h.kr/"  # 대치유수지.kr(퓨니코드)
TENNIS_TYPE = "8"  # type=8 = 테니스장(7=축구장 등 다른 종목)

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


def _months(today):
    """이번 달·다음 달 (연, 월) 두 개 — 페이지를 두 달치 조회하기 위함."""
    if today.month == 12:
        nxt = (today.year + 1, 1)
    else:
        nxt = (today.year, today.month + 1)
    return [(today.year, today.month), nxt]


def fetch_daechi_slots(settings):
    """대치유수지 빈자리(설정 기반 켜고끄기 + 시간/미래 필터)를 Slot 목록으로.

    settings: {"대치유수지": {받기, 평일/토/…}} 형태(설정표). 받기=False면 건너뜀.
    한 달 조회가 실패해도 다른 달은 계속(시설 전체가 죽지 않게).
    호출 빈도(15분·08~24시)는 이 함수가 아니라 main의 게이트가 통제한다.
    """
    cfg = settings.get(CENTER)
    if not cfg or not cfg.get("받기"):
        return []  # 설정표에서 끈 시설은 조회 안 함

    now = datetime.now(KST)
    session = make_session(HEADERS)
    result = []
    for year, month in _months(now.date()):
        try:
            r = session.get(BASE, params={
                "act": "reservation.reservation_list",
                "type": TENNIS_TYPE,
                "cyear": year,
                "cmonth": month,
            }, timeout=20)
            for slot in parse_daechi(r.text):
                slot_dt = datetime.strptime(slot.date + slot.time,
                                            "%Y-%m-%d%H:%M").replace(tzinfo=KST)
                if slot_dt > now and is_wanted_for(slot, cfg):
                    result.append(slot)
        except Exception as ex:  # 한 달 실패는 건너뛰고 계속
            print(f"[대치유수지 {year}-{month:02d} 조회 실패] {ex}")
    return result
