# scripts/debug_jamsil.py
"""잠실 '접수시간' 검증 — 시각에 따라 빈칸이 '예약불가'로 바뀌는지 (읽기 전용, 임시).

[가설] 잠실은 하루 중 일정 시간(사용자 관찰: 10~18시)에만 예약 접수 → 그 외 시각엔
       빈자리라도 '예약불가(status_e=접수불가시간)'로 표시된다.

[검증법] 같은 페이지를 ①접수시간(낮) ②비접수시간(저녁/밤)에 각각 조회해
        status_e(접수불가) 개수가 폭증하는지 비교한다. 각 실행이 현재 KST 시각을 찍는다.
        + 페이지에 접수시간 안내문구가 있으면 한 번에 확정.

[주의] 확인 끝나면 이 파일과 워크플로(cron 포함!) 반드시 삭제한다.
"""
import os
import re
import sys

sys.path.insert(0, ".")

from collections import Counter
from datetime import datetime

import requests
import urllib3

from src.esongpa import HEADERS, _login, _months, KST

urllib3.disable_warnings()

JAMSIL = "https://club.esongpa.or.kr"
LIST = "/page/rent/s07.od.list.php"

# 모든 시간칸: (시작시각, 상태클래스, 바로 뒤 글자). status_g/e는 글자가 바로 오고,
# status_y는 <a>가 끼어 글자가 빈 문자열로 잡힘(이미 '예약가능'으로 알고 있음).
CELL_RE = re.compile(r"<li>(\d{2}:\d{2})~\d{2}:\d{2}<span class='(status_[a-z]+)'>([^<]*)")

# 접수/예약 시간 안내가 있으면 가설 직접 확정
KEYWORDS = ["접수시간", "접수 시간", "예약시간", "예약 시간", "운영시간", "이용시간",
            "접수기간", "오전 10", "오후 6", "10:00", "18:00", "접수불가"]


def main():
    now = datetime.now(KST)
    print(f"\n{'#' * 60}\n현재 KST: {now.strftime('%Y-%m-%d %H:%M:%S (%A)')}\n{'#' * 60}")
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        print("로그인정보 없음(로컬 점검용).")
        return 0

    session = requests.Session()
    session.headers.update(HEADERS)
    print(f"로그인: {_login(session, JAMSIL)}")

    all_cells = []
    for ym in _months(now.date()):
        html = session.get(JAMSIL + LIST, params={"sch_sym": ym}, verify=False, timeout=20).text
        all_cells += CELL_RE.findall(html)
        # 안내문구 탐색(주변 텍스트 같이 출력)
        for kw in KEYWORDS:
            if kw in html:
                i = html.find(kw)
                near = re.sub(r"<[^>]+>|[ \t\r\n]+", " ", html[max(0, i - 50):i + 60]).strip()
                print(f"  [안내문구 {ym}] '{kw}' → ...{near}...")

    # 상태별 개수 + 글자(의미)
    print(f"\nstatus별 개수: {dict(Counter(c for _, c, _ in all_cells))}")
    labels = {}
    for _, c, txt in all_cells:
        if c not in labels and txt.strip():
            labels[c] = txt.strip()
    print(f"status 글자: {labels}")

    # ★ 핵심: status_e(접수불가) 시각분포 + 개수 — 비접수시간엔 폭증할 것
    e_hours = Counter(t for t, c, _ in all_cells if c == "status_e")
    print(f"★ status_e(접수불가) 시각분포: {dict(sorted(e_hours.items()))}  총 {sum(e_hours.values())}개")
    # 대조: status_y(예약가능) 시각분포 + 개수
    y_hours = Counter(t for t, c, _ in all_cells if c == "status_y")
    print(f"  status_y(예약가능) 시각분포: {dict(sorted(y_hours.items()))}  총 {sum(y_hours.values())}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
