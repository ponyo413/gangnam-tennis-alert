# scripts/debug_jamsil.py
"""잠실 시간칸 '재'확인 — 예약가능만이 아니라 모든 시간칸(마감 포함)을 본다 (읽기 전용, 임시).

[왜 다시 보나]
  앞선 확인은 '예약가능(status_y)' 칸만 셌다. 18·20시 타임이 그 순간 전부 '예약 마감'이었다면
  분포에서 통째로 빠진다 → "시간칸이 없다"고 잘못 결론날 수 있다.
  사용자님이 "18·20시 타임이 있다"고 하셨으니, 마감 칸까지 모두 모아 '시간칸 자체의 존재'를 검증한다.

[무엇을 보나]
  ① 전체 시간칸 분포(예약가능+마감 전부) — 저녁(17~21시) 칸이 실제로 있는가
  ② 상태클래스별 개수 + 의미(대표 칸의 글자) — status_y/r/g/e 가 각각 무슨 뜻인지
  ③ 저녁 칸이 있다면 어떤 상태인지(다 마감이라 안 보였던 것인지)

[주의] 확인이 끝나면 이 파일과 워크플로는 삭제한다.
"""
import os
import re
import sys

sys.path.insert(0, ".")

from collections import Counter
from datetime import datetime

import requests
import urllib3

from src.esongpa import HEADERS, _login, _months, ESONGPA_SITES, KST

urllib3.disable_warnings()

# 모든 시간칸: (시작시각, 상태클래스). 예약가능(status_y)·마감(status_r) 등 상태 불문 전부.
ALL_RE = re.compile(r"<li>(\d{2}:\d{2})~\d{2}:\d{2}<span class='(status_[a-z]+)'")


def check_site(site):
    center, base = site["center"], site["base"]
    print(f"\n{'=' * 60}\n[{center}] {base}  (목록 {site['list_page']})\n{'=' * 60}")

    session = requests.Session()
    session.headers.update(HEADERS)
    print(f"  로그인? {_login(session, base)}")

    all_cells = []                 # (시각, 상태) 누적
    sample_by_class = {}           # 상태클래스 → 대표 <li> 한 개(의미 파악용)
    for ym in _months(datetime.now(KST).date()):
        html = session.get(base + "/page/rent/" + site["list_page"],
                           params={"sch_sym": ym}, verify=False, timeout=20).text
        all_cells += ALL_RE.findall(html)
        for li in re.findall(r"<li>\d{2}:\d{2}~.*?</li>", html, re.DOTALL):
            m = re.search(r"class='(status_[a-z]+)'", li)
            if m and m.group(1) not in sample_by_class:
                sample_by_class[m.group(1)] = re.sub(r"[ \t\r\n]+", " ", li)[:160]

    # ① 전체 시간대 분포
    hours = Counter(t[:2] for t, _ in all_cells)
    print(f"\n  ① 전체 시간칸 분포(시작시각:개수): {dict(sorted(hours.items()))}")

    # ② 상태클래스별 개수
    print(f"  ② 상태클래스별 개수: {dict(Counter(c for _, c in all_cells))}")

    # ③ 저녁(17~21시) 칸이 있나 + 무슨 상태인가
    evening = Counter(f"{t[:2]}시/{c}" for t, c in all_cells if 17 <= int(t[:2]) <= 21)
    print(f"  ③ 저녁(17~21시) 칸 = {sum(evening.values())}개  상세={dict(sorted(evening.items()))}")

    print(f"  상태클래스 의미(대표 칸):")
    for cls, li in sample_by_class.items():
        print(f"     [{cls}] {li}")
    return center


def main():
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        print("→ 로그인 정보 없어 건너뜀(로컬 점검용).")
        return 0
    for site in ESONGPA_SITES:
        check_site(site)
    return 0


if __name__ == "__main__":
    sys.exit(main())
