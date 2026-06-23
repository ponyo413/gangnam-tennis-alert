# scripts/debug_jamsil.py
"""잠실(club.esongpa.or.kr) 실측 확인 — 송파를 '정상 기준'으로 나란히 대조 (읽기 전용, 임시).

[왜 만드나]
  지금 코드는 "잠실도 송파와 똑같이 생겼겠지"라는 '가정'으로만 만들어져 있고,
  잠실 사이트를 실제로 열어 빈자리 표가 읽히는지 한 번도 확인된 적이 없다.
  이 스크립트가 그 '통수 시험'이다.

[무엇을 보나]
  ① 빈자리가 운영 정규식으로 읽히는가(파싱) — 송파(기준)와 매칭 수 대조
  ② 시간대 분포 — 잠실에 '저녁(19~21시)' 칸이 실제로 있는가
  ③ 운영 시간필터(is_jamsil_wanted 등)를 통과하는 '실제 알림 대상'이 몇 건인가
     → 이게 0이면 빈자리는 읽혀도 알림은 안 간다는 뜻(시간대 설정 재상의 필요)

[주의] 확인이 끝나면 이 파일과 워크플로(.github/workflows/debug_jamsil.yml)는 삭제한다.
"""
import os
import re
import sys

sys.path.insert(0, ".")  # 저장소 루트에서 src 패키지를 찾도록 경로 추가

from collections import Counter
from datetime import datetime

import requests
import urllib3

# 운영 코드(esongpa.py)의 로그인·정규식·월계산·시설설정을 '그대로' 재사용(규칙 I: 중복 금지)
from src.esongpa import _SLOT_RE, HEADERS, _login, _months, ESONGPA_SITES, KST
from src.models import Slot

urllib3.disable_warnings()  # esongpa 사이트 SSL 체인 불완전(사이트 문제) 우회


def check_site(site):
    """한 시설(송파/잠실)에 로그인→이번달·다음달 목록 조회→구조·시간분포·필터통과 출력."""
    center, base, wanted_fn = site["center"], site["base"], site["wanted"]
    print(f"\n{'=' * 60}\n[{center}] {base}  (목록페이지 {site['list_page']})\n{'=' * 60}")

    session = requests.Session()
    session.headers.update(HEADERS)
    print(f"  로그인 성공(PHPSESSID 보유)? {_login(session, base)}")

    all_matches = []  # (시간, 날짜) 누적 — 이번달+다음달
    for ym in _months(datetime.now(KST).date()):
        url = base + "/page/rent/" + site["list_page"]
        r = session.get(url, params={"sch_sym": ym}, verify=False, timeout=20)
        matches = _SLOT_RE.findall(r.text)
        all_matches += matches
        print(f"  [{ym}] HTTP={r.status_code}  '예약가능' {('예약가능' in r.text)}  "
              f"정규식 매칭 {len(matches)}건")

    # ① 시간대 분포(시작시각) — 저녁(19~21시) 칸이 실제 있는지 한눈에
    hour_dist = Counter(t[:2] for t, _ in all_matches)
    print(f"\n  ① 빈자리 시간대 분포(시작시각:건수): {dict(sorted(hour_dist.items()))}")

    # ② 운영 시간필터를 통과하는 '실제 알림 대상' (미래분만 — 운영 봇과 동일 기준)
    now = datetime.now(KST)
    passed = []
    for t, d in all_matches:
        slot = Slot(center, "테니스장", d, t)
        slot_dt = datetime.strptime(d + t, "%Y-%m-%d%H:%M").replace(tzinfo=KST)
        if slot_dt > now and wanted_fn(slot):
            passed.append(f"{d} {t}")
    print(f"  ② 운영 필터 통과(=실제 알림 대상) = {len(passed)}건")
    print(f"     샘플: {passed[:10]}")

    return center, len(all_matches), len(passed)


def main():
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        print("→ 로그인 정보가 없어 조회 건너뜀(로컬 점검용 — 클라우드에서 실행해야 함).")
        return 0

    results = {}
    for site in ESONGPA_SITES:           # 송파·잠실 둘 다 (esongpa.py 등록 그대로)
        center, total, passed = check_site(site)
        results[center] = (total, passed)

    # ── 최종 판정 ──────────────────────────────────────────────
    print(f"\n{'#' * 60}\n[판정]")
    for center, (total, passed) in results.items():
        print(f"  · {center}: 빈자리 {total}건 읽힘 / 그중 '알림 대상' {passed}건")
    jamsil_total, jamsil_passed = results.get("잠실", (0, 0))
    if jamsil_total == 0:
        print("  [긴급] 잠실 빈자리가 0건 읽힘 → 구조/로그인 다름(코드 보완 필요)")
    elif jamsil_passed == 0:
        print("  [중요] 잠실 빈자리는 읽히나 '알림 대상'이 0건 → 원하는 시간대(저녁 등)가\n"
              "          잠실에 없을 수 있음. 시간대 설정을 사용자와 재상의 필요.")
    else:
        print("  [정상] 잠실 빈자리 읽힘 + 알림 대상도 있음 → 알림 정상 작동 확인")
    print('#' * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
