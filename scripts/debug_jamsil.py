# scripts/debug_jamsil.py
"""잠실(club.esongpa.or.kr) 실측 확인 — 송파를 '정상 기준'으로 나란히 대조 (읽기 전용, 임시).

[왜 만드나]
  지금 코드는 "잠실도 송파와 똑같이 생겼겠지"라는 '가정'으로만 만들어져 있고,
  잠실 사이트를 실제로 열어 빈자리 표가 읽히는지 한 번도 확인된 적이 없다.
  이 스크립트가 그 '통수 시험'이다 — 송파(이미 잘 되는 기준)와 잠실을 같은 코드로
  조회해 빈자리 매칭 개수를 비교한다.

[판정]
  · 송파>0, 잠실=0  → 잠실만 안 읽힘 = 잠실 구조/로그인이 송파와 다름(코드 보완 필요)
  · 둘 다 >0        → 잠실도 정상 작동(빈자리를 제대로 읽어옴)
  · 둘 다 0         → 마침 그 시간대에 빈자리가 없을 수 있음(시간 두고 재확인)

[주의] 확인이 끝나면 이 파일과 워크플로(.github/workflows/debug_jamsil.yml)는 삭제한다.
"""
import os
import re
import sys

sys.path.insert(0, ".")  # 저장소 루트에서 src 패키지를 찾도록 경로 추가

from datetime import datetime

import requests
import urllib3

# 운영 코드(esongpa.py)의 로그인·정규식·월계산을 '그대로' 재사용한다.
# (실제 봇이 쓰는 바로 그 로직으로 시험해야 결과가 의미 있음 — 규칙 I: 중복 금지)
from src.esongpa import _SLOT_RE, HEADERS, _login, _months, ESONGPA_SITES, KST

urllib3.disable_warnings()  # esongpa 사이트 SSL 체인 불완전(사이트 문제) 우회


def check_site(site):
    """한 시설(송파/잠실)에 로그인→이번달·다음달 목록 조회→구조를 출력. 매칭 총수 반환."""
    center, base = site["center"], site["base"]
    print(f"\n{'=' * 60}\n[{center}] {base}  (목록페이지 {site['list_page']})\n{'=' * 60}")

    # 운영 봇과 동일하게 시설별 세션 + 로그인
    session = requests.Session()
    session.headers.update(HEADERS)
    logged_in = _login(session, base)
    print(f"  로그인 성공(PHPSESSID 보유)? {logged_in}")
    print(f"  받은 쿠키: {[c.name for c in session.cookies]}")

    total = 0
    for ym in _months(datetime.now(KST).date()):
        url = base + "/page/rent/" + site["list_page"]
        r = session.get(url, params={"sch_sym": ym}, verify=False, timeout=20)
        html = r.text

        has_avail = "예약가능" in html          # 빈자리 표시 글자
        has_status_y = "status_y" in html        # 빈자리 칸 CSS 클래스
        matches = _SLOT_RE.findall(html)         # 운영 정규식으로 실제 추출
        total += len(matches)

        print(f"\n  [{ym}] HTTP={r.status_code}  HTML길이={len(html)}")
        print(f"        '예약가능' 글자 있음? {has_avail}   'status_y' 클래스 있음? {has_status_y}")
        print(f"        ▶ 운영 정규식 매칭 수 = {len(matches)}   샘플(시간,날짜) = {matches[:5]}")

        # 구조 단서: 이 페이지에 등장하는 status_* 클래스 종류
        kinds = sorted(set(re.findall(r"status_\w+", html)))
        print(f"        status_* 클래스 종류: {kinds[:10]}")

        # 실제 <li> 블록 2개를 직접 눈으로 — 송파와 모양이 같은지 비교용
        lis = re.findall(r"<li>.*?</li>", html, re.DOTALL)
        print(f"        <li> 블록 수: {len(lis)}")
        for li in lis[:2]:
            print(f"          · {re.sub(r'[ \t\r\n]+', ' ', li)[:150]}")

    print(f"\n  >>> [{center}] 빈자리 매칭 총합 = {total}건")
    return center, total


def main():
    has_login = bool(os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW"))
    print(f"로그인 정보(SONGPA_ID/PW) 준비됨? {has_login}")
    if not has_login:
        print("→ 로그인 정보가 없어 조회를 건너뜀(로컬에선 정상 — 클라우드 Secrets로 실행해야 함).")
        return 0  # 로컬 문법/임포트 점검용으로는 정상 종료

    results = {}
    for site in ESONGPA_SITES:           # 송파·잠실 둘 다 (esongpa.py에 등록된 그대로)
        center, total = check_site(site)
        results[center] = total

    # ── 최종 판정 ──────────────────────────────────────────────
    songpa, jamsil = results.get("송파", 0), results.get("잠실", 0)
    print(f"\n{'#' * 60}\n[판정]  송파(기준) {songpa}건  vs  잠실 {jamsil}건")
    if songpa > 0 and jamsil == 0:
        print("  [긴급] 송파는 읽히는데 잠실만 0 → 잠실 구조/로그인이 다름(코드 보완 필요)")
    elif jamsil > 0:
        print("  [정상] 잠실 빈자리가 운영 정규식으로 읽힘 → 파싱 정상 작동 확인")
    else:
        print("  [보류] 둘 다 0 → 마침 빈자리가 없을 수 있음(시간 두고 재확인 권장)")
    print('#' * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
