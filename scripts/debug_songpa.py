# -*- coding: utf-8 -*-
"""디버그: 송파 로그인 + 7월 빈자리 페이지 구조 확인 (GitHub Actions에서 Secrets로 실행).
   ※ 비밀번호는 출력하지 않음. 로그인 성공 여부와 빈자리 HTML 구조만 확인."""
import os, requests, re, sys, urllib3
urllib3.disable_warnings()
sys.stdout.reconfigure(encoding="utf-8")

ID = os.environ.get("SONGPA_ID", "")
PW = os.environ.get("SONGPA_PW", "")
print("ID 설정됨:", bool(ID), "| PW 설정됨:", bool(PW))  # 값은 출력 안 함, 존재만

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})

# 1) 로그인 시도
login = s.post(
    "https://spc.esongpa.or.kr/bbs/login_check.php",
    data={"mb_id": ID, "mb_password": PW, "url": "https://spc.esongpa.or.kr/"},
    verify=False, timeout=20, allow_redirects=True,
)
print("로그인 응답:", login.status_code, "| 최종URL:", login.url[:70])
print("세션쿠키:", [c.name for c in s.cookies])

# 2) 7월 빈자리 페이지 접근
r = s.get("https://spc.esongpa.or.kr/page/rent/s05.od.list.php?sch_sym=2026-07", verify=False, timeout=20)
t = r.text
print("빈자리페이지 len:", len(t))

# 3) 로그인 성공 판정
if "회원 로그인 후" in t:
    print(">>> ❌ 로그인 실패 (로그인 페이지로 튕김)")
else:
    print(">>> ✅ 로그인 성공 추정")
print("예약가능 횟수:", t.count("예약가능"), "| 예약완료 횟수:", t.count("예약완료"))

# 4) '예약가능' 주변 HTML 구조 (파서 작성용 — 개인정보 아님, 빈자리 셀 구조)
m = re.search(r"예약가능", t)
if m:
    print("=== '예약가능' 주변 HTML 구조 ===")
    print(t[max(0, m.start() - 300):m.start() + 60])
else:
    print("(예약가능 못 찾음 - 로그인 실패거나 구조 다름)")
