"""강남구 예약 사이트에서 포이·세곡 빈자리를 읽어온다. (A안: REST API 직접 호출)

분석 근거: docs/superpowers/notes-fetcher.md
구조: fetch_raw(원문 받기) → parse_slots(원문 → Slot 목록) → fetch_slots(전체 모으기)
"""
import time as _time
from datetime import datetime, timezone, timedelta

import requests

from src.models import Slot
from src.config import COURTS

# 빈자리 조회 API (한 번 호출 = 해당 월 전체 시간표)
ROOT = "https://life.gangnam.go.kr/"
API = ROOT + "rest/facilities/place_month_time_state_list"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://life.gangnam.go.kr/fmcs/54",
}

# 한국 표준시(KST). GitHub Actions는 UTC라 명시적으로 +9시간 고정.
KST = timezone(timedelta(hours=9))

# 호출 사이 간격(초) — 사이트에 부담 주지 않게 예의를 지킴
POLITE_DELAY = 0.3


def month_base_dates(today):
    """이번달(오늘)과 다음달 1일의 YYYYMMDD 두 개를 돌려준다.

    place_month_time_state_list는 base_date가 속한 '한 달'을 주므로,
    이번달+다음달을 보려면 두 날짜로 각각 호출한다.
    """
    this_month = today.strftime("%Y%m%d")
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return [this_month, nxt.strftime("%Y%m%d")]


def parse_slots(raw, court_name, place_name, now):
    """사이트 응답(raw)에서 '예약 가능(use_yn=N)'하고 '아직 안 지난' 시간만 Slot으로.

    - use_yn == 'N' 만 빈자리 (Y=예약완료, E=마감, U=예약불가, D=추첨)
    - now(현재 KST)보다 미래인 것만 (과거 날짜·지난 시간도 N으로 오므로 제외)
    """
    slots = []
    for item in raw:
        if item.get("use_yn") != "N":
            continue
        d = item.get("date")          # "20260622"
        t = item.get("start_time")    # "16:00"
        if not d or not t:
            continue
        slot_dt = datetime.strptime(d + t, "%Y%m%d%H:%M").replace(tzinfo=KST)
        if slot_dt <= now:
            continue  # 이미 지난 시간은 알릴 필요 없음
        iso_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"  # "2026-06-22"
        slots.append(Slot(court_name, place_name, iso_date, t))
    return slots


def fetch_raw(session, comcd, part, place, base_date):
    """한 코트·한 달치 빈자리 원문(JSON)을 사이트에서 받아온다."""
    resp = session.get(API, params={
        "company_code": comcd,
        "part_code": part,
        "place_code": place,
        "base_date": base_date,
        "rent_type": "",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_slots():
    """대상 코트 전부(이번달+다음달)의 현재 빈자리를 모아서 돌려준다.

    한 코트라도 조회에 성공하면 결과를 주고,
    모든 호출이 실패하면(사이트 다운 추정) 예외를 던져 호출부가 경고하게 한다.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    now = datetime.now(KST)
    base_dates = month_base_dates(now.date())

    result, success = [], 0
    for court in COURTS:
        for place_cd, place_nm in court["places"].items():
            for base_date in base_dates:
                try:
                    raw = fetch_raw(session, court["comcd"], court["part"], place_cd, base_date)
                    success += 1
                    result.extend(parse_slots(raw, court["center"], place_nm, now))
                except Exception as e:  # 한 코트 실패는 건너뛰고 계속
                    print(f"[조회 실패] {court['center']} {place_nm} {base_date}: {e}")
                _time.sleep(POLITE_DELAY)

    if success == 0:
        raise RuntimeError("모든 코트 조회 실패 — 사이트 접속 불가로 추정")
    return result
