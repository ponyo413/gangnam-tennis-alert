# src/esongpa.py
"""esongpa(송파·잠실) 빈자리 조회 — 로그인 + HTML 파싱 공용.

시설별 차이(주소·목록페이지·원하는 시간대)는 ESONGPA_SITES 설정으로 분리.
로그인 ID/비번은 환경변수(SONGPA_ID/SONGPA_PW)에서만 가져온다(코드에 안 적음).
"""
import os
import re
from datetime import datetime, timezone, timedelta

import requests
import urllib3

from src.models import Slot
from src.filters import is_songpa_wanted

urllib3.disable_warnings()  # esongpa 사이트 SSL 체인 불완전(사이트 문제) 우회

KST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# 빈자리(예약가능) 한 칸: <li>HH:MM~HH:MM<span class='status_y'>...('코트','날짜')...예약가능
_SLOT_RE = re.compile(
    r"<li>(\d{2}:\d{2})~\d{2}:\d{2}<span class='status_y'>"
    r"<a[^>]*?fn_rent_odchk1\([^,]*,\s*'(\d{4}-\d{2}-\d{2})'\)[^>]*?>예약가능",
    re.DOTALL,
)

# 시설 설정 — 잠실은 다음 작업에서 한 줄 추가
ESONGPA_SITES = [
    {"center": "송파", "base": "https://spc.esongpa.or.kr",
     "list_page": "s05.od.list.php", "wanted": is_songpa_wanted},
]


def _login(session, base):
    """해당 시설(base 도메인)에 로그인. 성공하면 True(PHPSESSID 보유)."""
    user = os.environ.get("SONGPA_ID", "")
    pw = os.environ.get("SONGPA_PW", "")
    if not (user and pw):
        return False
    session.post(base + "/bbs/login_check.php",
                 data={"mb_id": user, "mb_password": pw, "url": base + "/"},
                 verify=False, timeout=20)
    return any(c.name == "PHPSESSID" for c in session.cookies)


def parse_esongpa(html, center):
    """HTML에서 '예약가능' 슬롯을 Slot 목록으로 추출(코트명 '테니스장' 고정)."""
    return [Slot(center, "테니스장", date_str, time_str)
            for time_str, date_str in _SLOT_RE.findall(html)]


def _months(today):
    """이번달·다음달 'YYYY-MM' 두 개."""
    this_m = today.strftime("%Y-%m")
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return [this_m, nxt.strftime("%Y-%m")]


def fetch_esongpa_slots():
    """등록된 모든 esongpa 시설의 빈자리(시설별 시간필터 적용)를 Slot 목록으로.

    ID/비번 미설정이면 빈 목록(비활성). 한 시설 로그인 실패는 예외.
    """
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        return []

    now = datetime.now(KST)
    result = []
    for site in ESONGPA_SITES:
        # 도메인마다 쿠키가 분리될 수 있어 시설별로 세션+로그인
        session = requests.Session()
        session.headers.update(HEADERS)
        if not _login(session, site["base"]):
            raise RuntimeError(f"{site['center']} 로그인 실패 (ID/비번 확인)")
        for ym in _months(now.date()):
            url = site["base"] + "/page/rent/" + site["list_page"]
            r = session.get(url, params={"sch_sym": ym}, verify=False, timeout=20)
            for slot in parse_esongpa(r.text, site["center"]):
                slot_dt = datetime.strptime(slot.date + slot.time, "%Y-%m-%d%H:%M").replace(tzinfo=KST)
                if slot_dt > now and site["wanted"](slot):
                    result.append(slot)
    return result
