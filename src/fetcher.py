"""강남구 예약 사이트에서 포이·세곡 빈자리를 읽어온다. (A안: REST API 직접 호출)

분석 근거: docs/superpowers/notes-fetcher.md
빈자리 = ① 그 '날짜'가 예약가능 상태(state_cd 10/11) AND ② 그 '시간칸'이 빔(use_yn='N') AND ③ 미래
  - ① place_month_state_list (날짜별 예약가능 여부)
  - ② place_month_time_state_list (시간칸별 빈/참)
구조: fetch_state_raw/fetch_time_raw(원문) → parse_open_dates/parse_slots(해석) → fetch_slots(전체)
"""
import time as _time
from datetime import datetime, timezone, timedelta

import requests

from src.models import Slot
from src.config import COURTS, OPEN_STATE_CODES, FACILITIES

ROOT = "https://life.gangnam.go.kr/"
# 날짜별 '예약 가능 여부' (한 달치) — state_cd 10/11=예약가능
STATE_API = ROOT + "rest/facilities/place_month_state_list"
# 시간칸별 '빈/참' (한 달치) — use_yn 'N'=빈칸
TIME_API = ROOT + "rest/facilities/place_month_time_state_list"

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

    각 월별 API는 base_date가 속한 '한 달'을 주므로, 이번달+다음달을 보려면 두 날짜로 호출.
    """
    this_month = today.strftime("%Y%m%d")
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return [this_month, nxt.strftime("%Y%m%d")]


def parse_open_dates(state_raw):
    """날짜별 상태 응답에서 '온라인 예약 가능'한 날짜(ISO 문자열) 집합을 돌려준다.

    state_cd 10/11=예약가능 → 포함. 15=추첨·20=마감/예약불가·30=휴관 → 제외.
    (응답의 date는 이미 "2026-06-27" ISO 형식)
    """
    return {x.get("date") for x in state_raw if x.get("state_cd") in OPEN_STATE_CODES}


def parse_slots(raw, court_name, place_name, now, open_dates):
    """시간칸 응답(raw)에서 진짜 빈자리만 Slot으로.

    조건: use_yn=='N'(빈칸) AND 그 날짜가 open_dates(예약가능)에 있음 AND now보다 미래.
    """
    slots = []
    for item in raw:
        if item.get("use_yn") != "N":
            continue
        d = item.get("date")          # "20260627"
        t = item.get("start_time")    # "20:00"
        if not d or not t:
            continue
        iso_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"  # "2026-06-27"
        if iso_date not in open_dates:
            continue  # ★ 날짜가 '예약가능' 상태가 아니면 빈칸이어도 제외
        slot_dt = datetime.strptime(d + t, "%Y%m%d%H:%M").replace(tzinfo=KST)
        if slot_dt <= now:
            continue  # 이미 지난 시간 제외
        slots.append(Slot(court_name, place_name, iso_date, t))
    return slots


def _fetch_json(session, url, comcd, part, place, base_date):
    """공통: 한 코트·한 달치 원문(JSON)을 받아온다."""
    resp = session.get(url, params={
        "company_code": comcd,
        "part_code": part,
        "place_code": place,
        "base_date": base_date,
        "rent_type": "",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_slots():
    """대상 코트 전부(이번달+다음달)의 진짜 빈자리를 모아서 돌려준다.

    각 코트·월마다: 날짜상태(예약가능 날짜) + 시간칸(빈칸)을 함께 조회해 결합.
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
                    # ① 예약가능 날짜
                    state_raw = _fetch_json(session, STATE_API, court["comcd"], court["part"], place_cd, base_date)
                    open_dates = parse_open_dates(state_raw)
                    # ② 빈 시간칸 → ①과 결합
                    time_raw = _fetch_json(session, TIME_API, court["comcd"], court["part"], place_cd, base_date)
                    success += 1
                    result.extend(parse_slots(time_raw, court["center"], place_nm, now, open_dates))
                except Exception as e:  # 한 코트 실패는 건너뛰고 계속
                    print(f"[조회 실패] {court['center']} {place_nm} {base_date}: {e}")
                _time.sleep(POLITE_DELAY)

    if success == 0:
        raise RuntimeError("모든 코트 조회 실패 — 사이트 접속 불가로 추정")
    return result


# ─────────────────────────────────────────────────────────────
# 신청기간 알림: 시설 신청상태 조회 (place_detail)
# ─────────────────────────────────────────────────────────────
DETAIL_API = ROOT + "rest/facilities/place_detail"


def parse_status(detail):
    """place_detail 응답에서 신청 상태 정보(상태·접수기간·이용기간)만 추린다."""
    return {
        "state": detail.get("state_nm", ""),
        "receipt": detail.get("receipt_period", ""),
        "period": detail.get("period", ""),
    }


def fetch_facility_status():
    """포이·세곡의 신청 상태를 {시설명: {state, receipt, period}}로 돌려준다.

    한 시설 조회가 실패하면 그 시설만 건너뛴다.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    result = {}
    for f in FACILITIES:
        try:
            resp = session.get(DETAIL_API, params={
                "company_code": f["comcd"],
                "part_code": f["part"],
                "place_code": f["place"],
            }, timeout=15)
            resp.raise_for_status()
            result[f["name"]] = parse_status(resp.json())
        except Exception as e:
            print(f"[상태 조회 실패] {f['name']}: {e}")
        _time.sleep(POLITE_DELAY)
    return result
