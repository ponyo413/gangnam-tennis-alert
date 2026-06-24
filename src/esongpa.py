# src/esongpa.py
"""esongpa(송파·잠실) 빈자리 조회 — 로그인 + HTML 파싱 공용.

시설별 차이(주소·목록페이지)는 ESONGPA_SITES로 분리.
시간대/켜고끄기는 settings.yaml(설정표)에서 받아 is_wanted_for로 거른다.
로그인 ID/비번은 환경변수(SONGPA_ID/SONGPA_PW)에서만 가져온다(코드에 안 적음).
"""
import os
import re
from datetime import datetime, timezone, timedelta

import requests
import urllib3

from src.models import Slot
from src.filters import is_wanted_for

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

# 모든 시간칸의 상태클래스(status_y=예약가능 / status_e=접수불가 / status_g=예약완료)를
# 뽑는다 — "지금이 접수시간인지"를 데이터로 판정(_is_intake_closed)하는 데 쓴다.
_STATUS_RE = re.compile(r"<li>\d{2}:\d{2}~\d{2}:\d{2}<span class='(status_[a-z]+)'")

# 시설 설정 — 주소·목록페이지만(시간대·켜고끄기는 settings.yaml 설정표에서)
ESONGPA_SITES = [
    {"center": "송파", "base": "https://spc.esongpa.or.kr", "list_page": "s05.od.list.php"},
    {"center": "잠실", "base": "https://club.esongpa.or.kr", "list_page": "s07.od.list.php"},
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


def _is_intake_closed(html):
    """지금이 esongpa '접수시간이 아닌지'(빈칸이 전부 접수불가로 잠겼는지) 판단한다.

    잠실은 낮 접수시간에만 예약가능(status_y)이 뜨고, 저녁·밤엔 비어 있는 칸도
    전부 접수불가(status_e)로 잠긴다(2026-06-23 디버그 실측). 그래서:
      - 예약가능(status_y)이 하나라도 있으면 → 접수시간(열림), False
      - 예약가능 0 + 접수불가(status_e)가 1개 이상 → 접수 닫힘, True
      - 예약가능 0 + 접수불가 0(빈칸 없이 전부 예약완료) → 닫힘 아님(빈자리 0이 사실), False
    시각을 직접 정하지 않고 응답 데이터로 판단하므로, 시설이 접수시간을 바꿔도 알아서 맞춰진다.
    """
    statuses = _STATUS_RE.findall(html)
    available = statuses.count("status_y")     # 예약가능(빈칸 중 받을 수 있는 칸)
    unavailable = statuses.count("status_e")   # 접수불가(빈칸이지만 지금은 못 받는 칸)
    return available == 0 and unavailable > 0


def _months(today):
    """이번달·다음달 'YYYY-MM' 두 개."""
    this_m = today.strftime("%Y-%m")
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return [this_m, nxt.strftime("%Y-%m")]


def fetch_esongpa_slots(settings, previous_slots=()):
    """등록된 esongpa 시설의 빈자리(설정 기반 켜고끄기 + 시간필터)를 Slot 목록으로.

    settings: {"송파": {...}, "잠실": {...}} 형태(설정표). 받기=False면 그 시설 건너뜀.
    previous_slots: 직전에 저장된 전체 빈자리 목록. 어떤 시설이 '접수 닫힘'(저녁)이면
        그 시설은 새로 조회한 0건 대신 직전 빈자리를 그대로 유지한다(가짜 변동 알림 방지).
    ID/비번 미설정이면 빈 목록(비활성). 한 시설 실패는 건너뛰고 나머지는 계속.
    """
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        return []

    now = datetime.now(KST)
    result = []
    for site in ESONGPA_SITES:
        center = site["center"]
        cfg = settings.get(center)
        if not cfg or not cfg.get("받기"):
            continue  # 설정표에서 끈 시설은 조회 자체를 안 함
        # 한 시설이 실패해도 다른 시설 조회는 계속(잠실 실패해도 송파는 진행)
        try:
            # 도메인마다 쿠키가 분리될 수 있어 시설별로 세션+로그인
            session = requests.Session()
            session.headers.update(HEADERS)
            if not _login(session, site["base"]):
                raise RuntimeError(f"{center} 로그인 실패 (ID/비번 확인)")
            site_slots = []   # 이 시설에서 새로 뽑은 빈자리(원하는 시간대 + 미래)
            pages = []        # 이 시설의 모든 달 HTML — '접수 닫힘' 판정에 쓴다
            for ym in _months(now.date()):
                url = site["base"] + "/page/rent/" + site["list_page"]
                r = session.get(url, params={"sch_sym": ym}, verify=False, timeout=20)
                pages.append(r.text)
                for slot in parse_esongpa(r.text, center):
                    slot_dt = datetime.strptime(slot.date + slot.time, "%Y-%m-%d%H:%M").replace(tzinfo=KST)
                    if slot_dt > now and is_wanted_for(slot, cfg):
                        site_slots.append(slot)
            # 접수 닫힘(저녁): 빈칸이 전부 접수불가라 이 시각 조회 결과(0건)는 못 믿는다.
            # → 직전에 보던 이 시설 빈자리를 그대로 유지(낮 접수시간이 되면 다시 갱신).
            if _is_intake_closed("".join(pages)):
                # 단, 이미 지나간 시각은 버린다(저녁 동안 과거 슬롯이 요약 메시지에 남지 않게)
                kept = [s for s in previous_slots
                        if s.court == center
                        and datetime.strptime(s.date + s.time, "%Y-%m-%d%H:%M").replace(tzinfo=KST) > now]
                result += kept
                print(f"[{center} 접수시간 아님 → 직전 {len(kept)}건 유지]")
            else:
                result += site_slots
        except Exception as e:
            print(f"[{center} 조회 실패] {e}")
    return result
