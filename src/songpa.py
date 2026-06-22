"""송파테니스장 빈자리 조회 (로그인 + HTML 파싱).

강남(REST API)과 달리 송파는 로그인 후 화면(HTML)을 읽어야 함.
- 로그인: mb_id/mb_password → /bbs/login_check.php
- 조회: /page/rent/s05.od.list.php?sch_sym=YYYY-MM
- 빈자리 판정: <li> 안의 class='status_y' + '예약가능'
- ID/비번은 환경변수(SONGPA_ID/SONGPA_PW=GitHub Secrets)에서만
"""
import os
import re
from datetime import datetime, timezone, timedelta

import requests
import urllib3

from src.models import Slot

urllib3.disable_warnings()  # 송파 사이트 SSL 인증서 체인 불완전(사이트 문제) 우회

KST = timezone(timedelta(hours=9))
BASE = "https://spc.esongpa.or.kr"
LOGIN_URL = BASE + "/bbs/login_check.php"
LIST_URL = BASE + "/page/rent/s05.od.list.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# 빈자리(예약가능) 한 칸: <li>HH:MM~HH:MM<span class='status_y'>...('코트', '날짜')...예약가능
_SLOT_RE = re.compile(
    r"<li>(\d{2}:\d{2})~\d{2}:\d{2}<span class='status_y'>"
    r"<a[^>]*?fn_rent_odchk1\([^,]*,\s*'(\d{4}-\d{2}-\d{2})'\)[^>]*?>예약가능",
    re.DOTALL,
)


def _login(session):
    """송파 로그인. 성공하면 True (세션 쿠키 보유)."""
    user = os.environ.get("SONGPA_ID", "")
    pw = os.environ.get("SONGPA_PW", "")
    if not (user and pw):
        return False
    session.post(LOGIN_URL,
                 data={"mb_id": user, "mb_password": pw, "url": BASE + "/"},
                 verify=False, timeout=20)
    return any(c.name == "PHPSESSID" for c in session.cookies)


def parse_songpa(html, court_name="테니스장"):
    """HTML에서 '예약가능' 슬롯을 (날짜, 시간) Slot 목록으로 추출."""
    slots = []
    for time_str, date_str in _SLOT_RE.findall(html):
        slots.append(Slot("송파", court_name, date_str, time_str))
    return slots


def _months(today):
    """이번달·다음달의 'YYYY-MM' 두 개."""
    this_m = today.strftime("%Y-%m")
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return [this_m, nxt.strftime("%Y-%m")]


def fetch_songpa_slots():
    """송파 빈자리(예약가능)를 Slot 목록으로. 로그인 실패 시 예외.

    ID/비번이 없으면(미설정) 빈 목록(송파 비활성).
    """
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        return []  # 송파 미설정 — 조용히 건너뜀

    session = requests.Session()
    session.headers.update(HEADERS)
    if not _login(session):
        raise RuntimeError("송파 로그인 실패 (ID/비번 확인 필요)")

    now = datetime.now(KST)
    result = []
    for ym in _months(now.date()):
        r = session.get(LIST_URL, params={"sch_sym": ym}, verify=False, timeout=20)
        for slot in parse_songpa(r.text):
            # 미래 시간만 (지난 건 제외)
            slot_dt = datetime.strptime(slot.date + slot.time, "%Y-%m-%d%H:%M").replace(tzinfo=KST)
            if slot_dt > now:
                result.append(slot)
    return result
