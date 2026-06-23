# 잠실 테니스장 추가 & 빈자리 요약 알림 — 구현 공정표

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 잠실 유수지 테니스장을 빈자리 알림에 추가하고(송파와 같은 esongpa 시스템), "지금 비어있는 자리"를 매일 아침 8시에 요약 알림하는 기능을 더한다.

**Architecture:** 송파 전용 `songpa.py`를 시설 독립적인 `esongpa.py`(로그인·조회·파싱 공용 + 시설 설정 목록)로 일반화한다. 잠실은 설정 한 줄로 추가. 빈자리 요약은 직전기록(state) 없이 "현재 상태"만 읽어 별도 워크플로(매일 08:00 KST)로 발송한다.

**Tech Stack:** Python 3.13, requests, python-dotenv, pytest, GitHub Actions(cron).

**전제(설계서):** `docs/superpowers/specs/2026-06-23-jamsil-and-vacancy-summary-design.md`

---

## 파일 구조

| 파일 | 책임 | 변경 |
|---|---|---|
| `src/esongpa.py` | 송파·잠실 공용 조회(로그인+파싱) + 시설 설정 | 신규(songpa.py 대체) |
| `src/songpa.py` | (제거 — esongpa.py로 흡수) | 삭제 |
| `src/filters.py` | 시간대 필터 | `is_jamsil_wanted` 추가 |
| `src/notifier.py` | 텔레그램 메시지 | `format_summary` 추가 |
| `src/main.py` | 흐름 조율 | `run_summary` + 모드 분기 추가 |
| `.github/workflows/daily-summary.yml` | 매일 요약 워크플로 | 신규 |
| `tests/test_esongpa.py` | esongpa 파싱 회귀/잠실 | 신규 |
| `tests/test_filters.py` | 필터 테스트 | 잠실 케이스 추가 |
| `tests/test_notifier.py` | 메시지 테스트 | 요약 케이스 추가 |

> 주의: `main.py` 의 `from src.songpa import fetch_songpa_slots` 와 `is_songpa_wanted` 사용부도 함께 바꾼다(Task 3).

---

## Task 1: 잠실 실제 구조 검증 (탐색 — 코드 작성 전 확인)

**목적:** "송파와 같다"는 가정이 맞는지 실측. 로그인 경로/HTML/정규식이 동일한지 확인. 다르면 Task 5의 파서를 조정.

**Files:** 임시 `_scratch/probe_jamsil.py` (이미 존재)

- [ ] **Step 1: 송파 ID/비번을 환경에 준비**

로컬 `.env`에 두 줄을 임시 추가(실행자/사용자):
```
SONGPA_ID=<송파 아이디>
SONGPA_PW=<송파 비밀번호>
```
(또는 GitHub Actions에서 `workflow_dispatch`로 확인 — Secrets에 이미 있음)

- [ ] **Step 2: 로그인 후 잠실 구조 확인**

Run: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python _scratch/probe_jamsil.py`
확인: `[로그인] PHPSESSID 있음? True` / `'예약가능' 포함? True` / `status_y 포함? True` / `송파 정규식 매칭 수 > 0`

- [ ] **Step 3: 판정 기록**

- 모두 충족 → 송파 `_SLOT_RE`/로그인 그대로 재사용(이 공정표대로).
- 다르면 → 잠실 HTML을 `tests/fixtures/jamsil_sample.html`로 저장, Task 5에서 잠실 전용 정규식 도출. ERRORS.md/작업메모에 차이 기록.

> 탐색 Task라 커밋 없음.

---

## Task 2: 송파 파싱 회귀 테스트 (공용화 전 안전망)

**목적:** 공용화로 송파 동작이 깨지지 않도록 현재 파싱 동작을 고정 HTML로 박제.

**Files:** Create `tests/test_esongpa.py`

- [ ] **Step 1: 실패하는 회귀 테스트 작성**

```python
# tests/test_esongpa.py
"""esongpa(송파·잠실) 파싱 — 고정 HTML로 동작 박제."""
from src.esongpa import parse_esongpa

SAMPLE_HTML = (
    "<ul>"
    "<li>19:00~20:00<span class='status_y'>"
    "<a href=\"#\" onclick=\"fn_rent_odchk1('A', '2026-07-04')\">예약가능</a></span></li>"
    "<li>20:00~21:00<span class='status_n'>"
    "<a href=\"#\">예약완료</a></span></li>"
    "</ul>"
)


def test_parse_extracts_only_available_slots():
    slots = parse_esongpa(SAMPLE_HTML, "송파")
    assert len(slots) == 1
    s = slots[0]
    assert s.court == "송파"
    assert s.date == "2026-07-04"
    assert s.time == "19:00"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_esongpa.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.esongpa'` (아직 없음)

> 통과는 Task 3에서. 커밋도 Task 3과 함께.

---

## Task 3: esongpa 공용화 (songpa.py → esongpa.py)

**목적:** 송파 로직을 시설 독립적으로 일반화. 이 단계에선 송파만 등록(잠실은 Task 5).

**Files:** Create `src/esongpa.py` / Delete `src/songpa.py` / Modify `src/main.py`

- [ ] **Step 1: esongpa.py 작성**

```python
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

# 시설 설정 — 잠실은 Task 5에서 한 줄 추가
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
```

- [ ] **Step 2: songpa.py 삭제** — Run: `git rm src/songpa.py`

- [ ] **Step 3: main.py 호출부 교체**

- `from src.songpa import fetch_songpa_slots` → `from src.esongpa import fetch_esongpa_slots`
- `from src.filters import is_wanted_time, is_songpa_wanted` → `from src.filters import is_wanted_time`
- `run_vacancy_alert` 송파 블록 교체:

before:
```python
    wanted = [s for s in current_all if is_wanted_time(s)]
    # 송파(로그인 필요) — 실패해도 강남 알림은 계속 진행
    try:
        wanted += [s for s in fetch_songpa_slots() if is_songpa_wanted(s)]
    except Exception as e:
        print(f"[송파 조회 실패] {e}")
```
after:
```python
    wanted = [s for s in current_all if is_wanted_time(s)]
    # esongpa(송파·잠실, 로그인 필요) — 실패해도 강남 알림은 계속 진행
    try:
        wanted += fetch_esongpa_slots()  # 시설별 시간필터는 내부에서 적용
    except Exception as e:
        print(f"[esongpa 조회 실패] {e}")
```

- [ ] **Step 4: 회귀 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: PASS (Task 2 회귀 + 기존 전체)

- [ ] **Step 5: 커밋**

```bash
git add src/esongpa.py tests/test_esongpa.py src/main.py
git rm src/songpa.py
git commit -m "refactor: 송파 조회를 esongpa 공용 모듈로 일반화(잠실 추가 준비)"
```

---

## Task 4: 잠실 시간대 필터 `is_jamsil_wanted`

**Files:** Modify `src/filters.py`, `tests/test_filters.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_filters.py 에 추가
from src.filters import is_jamsil_wanted
from src.models import Slot


def test_jamsil_weekday_evening_allowed():
    # 2026-07-01 수요일 — 저녁 20시 허용
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-01", "20:00")) is True


def test_jamsil_weekday_morning_rejected():
    # 평일 오전 10시 제외(토요일 아님)
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-01", "10:00")) is False


def test_jamsil_saturday_morning_allowed():
    # 2026-07-04 토요일 — 오전 08·10시 허용
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "08:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "10:00")) is True


def test_jamsil_daytime_weekday_rejected():
    # 평일 낮 14시 제외
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-01", "14:00")) is False
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_filters.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_jamsil_wanted'`

- [ ] **Step 3: 필터 구현**

```python
# src/filters.py 에 추가 (상단 from datetime import date 이미 있음)
def is_jamsil_wanted(slot: Slot) -> bool:
    """잠실: 매일 저녁 19~21시 시작 + 토요일 08·10시 시작."""
    hour = int(slot.time.split(":")[0])
    if EVENING_START <= hour < EVENING_END:  # 19·20·21시(=저녁 7~10시)
        return True
    y, m, d = (int(x) for x in slot.date.split("-"))
    if date(y, m, d).weekday() == 5 and slot.time in ("08:00", "10:00"):  # 토=5
        return True
    return False
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_filters.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add src/filters.py tests/test_filters.py
git commit -m "feat: 잠실 시간대 필터(매일 저녁+토 오전) 추가"
```

---

## Task 5: 잠실을 시설 목록에 추가

**Files:** Modify `src/esongpa.py`, `tests/test_esongpa.py`

> Task 1에서 잠실 HTML이 송파와 다르다고 판정됐으면, 먼저 `parse_esongpa`가 잠실 패턴도 처리하도록 정규식을 조정(또는 시설별 파서 지정)하고 테스트를 추가한 뒤 진행.

- [ ] **Step 1: 잠실 파싱 테스트 추가(송파와 동일 구조 가정)**

```python
# tests/test_esongpa.py 에 추가
def test_parse_jamsil_same_structure():
    html = (
        "<li>21:00~22:00<span class='status_y'>"
        "<a href=\"#\" onclick=\"fn_rent_odchk1('B', '2026-07-04')\">예약가능</a></span></li>"
    )
    slots = parse_esongpa(html, "잠실")
    assert len(slots) == 1
    assert slots[0].court == "잠실"
    assert slots[0].date == "2026-07-04"
    assert slots[0].time == "21:00"
```

- [ ] **Step 2: 통과 확인** — Run: `pytest tests/test_esongpa.py::test_parse_jamsil_same_structure -v` → PASS (center만 다르므로 통과)

- [ ] **Step 3: ESONGPA_SITES에 잠실 추가**

```python
# src/esongpa.py — import에 is_jamsil_wanted 추가
from src.filters import is_songpa_wanted, is_jamsil_wanted

# ESONGPA_SITES 에 한 줄 추가
ESONGPA_SITES = [
    {"center": "송파", "base": "https://spc.esongpa.or.kr",
     "list_page": "s05.od.list.php", "wanted": is_songpa_wanted},
    {"center": "잠실", "base": "https://club.esongpa.or.kr",
     "list_page": "s07.od.list.php", "wanted": is_jamsil_wanted},
]
```

- [ ] **Step 4: 전체 테스트** — Run: `pytest tests/ -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add src/esongpa.py tests/test_esongpa.py
git commit -m "feat: 잠실 유수지 테니스장을 esongpa 시설 목록에 추가"
```

---

## Task 6: 빈자리 요약 메시지 `format_summary`

**Files:** Modify `src/notifier.py`, `tests/test_notifier.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_notifier.py 에 추가
from src.notifier import format_summary
from src.models import Slot


def test_summary_lists_slots_sorted():
    slots = [
        Slot("세곡", "3번코트", "2026-07-02", "21:00"),
        Slot("송파", "테니스장", "2026-07-04", "08:00"),
    ]
    msg = format_summary(slots)
    assert "빈자리 현황" in msg
    assert "세곡" in msg and "송파" in msg
    assert "2026-07-02" in msg


def test_summary_empty_says_none():
    msg = format_summary([])
    assert "빈자리 없음" in msg
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_notifier.py -v` → FAIL (`cannot import name 'format_summary'`)

- [ ] **Step 3: 구현**

```python
# src/notifier.py 에 추가 (RESERVE_URL 이미 import됨)
def format_summary(slots: list[Slot]) -> str:
    """매일 1회 '현재 빈자리 전체' 요약 메시지. 빈 목록이면 '없음' 한 줄."""
    if not slots:
        return "🎾 [오늘의 빈자리 현황]\n현재 빈자리 없음"
    lines = ["🎾 [오늘의 빈자리 현황]"]
    for s in sorted(slots, key=lambda x: (x.court, x.date, x.time)):
        lines.append(f"🏟 {s.court} {s.place}  📅 {s.date} {s.time}")
    lines.append(f"👉 예약: {RESERVE_URL}")
    return "\n".join(lines)
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_notifier.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: 빈자리 현황 요약 메시지 포맷 추가"
```

---

## Task 7: 요약 진입점 `run_summary` + 모드 분기

**Files:** Modify `src/main.py`

- [ ] **Step 1: run_summary + 모드 분기 작성**

`src/main.py` import에 `format_summary` 추가:
```python
from src.notifier import format_message, send_telegram, format_application_message, format_summary
```

함수 추가:
```python
def run_summary():
    """매일 1회: 현재 '원하는 시간대' 빈자리 전체를 요약 발송(직전기록 불필요)."""
    wanted = []
    try:
        wanted += [s for s in fetch_slots() if is_wanted_time(s)]
    except Exception as e:
        print(f"[요약-강남 조회 실패] {e}")
    try:
        wanted += fetch_esongpa_slots()  # 송파·잠실(시설별 필터 적용)
    except Exception as e:
        print(f"[요약-esongpa 조회 실패] {e}")
    send_telegram(format_summary(wanted))
    print(f"[요약 발송] {len(wanted)}건")
```

`main()` 모드 분기로 교체:
```python
def main() -> int:
    # 인자 'summary' → 일일 요약, 그 외 → 기존 취소표/신청 감시
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if mode == "summary":
        run_summary()
    else:
        run_vacancy_alert()
        run_application_alert()
    return 0
```

- [ ] **Step 2: 전체 테스트** — Run: `pytest tests/ -v` → PASS

- [ ] **Step 3: 요약 모드 손수 실행(로컬, ID/비번 있을 때)**

Run: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m src.main summary`
Expected: 콘솔 `[요약 발송] N건` + 텔레그램 요약 1통(없으면 '현재 빈자리 없음').

- [ ] **Step 4: 커밋**

```bash
git add src/main.py
git commit -m "feat: 일일 빈자리 요약 진입점(summary 모드) 추가"
```

---

## Task 8: 일일 요약 워크플로

**Files:** Create `.github/workflows/daily-summary.yml`

- [ ] **Step 1: 워크플로 작성**

```yaml
# .github/workflows/daily-summary.yml
# 매일 아침 8시(KST) '현재 빈자리 전체'를 요약 1통 발송 — 직전기록(state) 불필요
name: 빈자리 요약

on:
  schedule:
    - cron: "0 23 * * *"   # UTC 23:00 = KST 08:00
  workflow_dispatch:

jobs:
  summary:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: 라이브러리 설치
        run: pip install -r requirements.txt
      - name: 빈자리 요약 발송
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          SONGPA_ID: ${{ secrets.SONGPA_ID }}
          SONGPA_PW: ${{ secrets.SONGPA_PW }}
        run: python -m src.main summary
```

- [ ] **Step 2: 커밋**

```bash
git add .github/workflows/daily-summary.yml
git commit -m "ci: 매일 아침 8시 빈자리 요약 워크플로 추가"
```

---

## Task 9: 통합 검증 & 배포 준비

- [ ] **Step 1: 전체 테스트 + 잠실 실측(가능 시)**

Run: `pytest tests/ -v` → 전체 PASS
(ID/비번 있으면) Run: `python _scratch/probe_jamsil.py` 로 잠실 로그인·매칭 재확인.

- [ ] **Step 2: 변경 요약 + 사용자 승인 요청 (규칙 D)**

바뀐 파일·동작 변화를 쉬운 말로 보고하고 "1층(main)에 배포할까요?" 승인 요청.

- [ ] **Step 3: 승인 후 push + 배포 확인**

```bash
git log origin/main..HEAD --oneline   # 올라갈 커밋 확인(형제 커밋 동반 여부)
git push origin main
```
배포 후: GitHub Actions에서 `빈자리 요약` 을 `workflow_dispatch`로 1회 수동 실행 → 텔레그램 수신 확인. 잠실이 5분 워크플로(`빈자리 점검`)에도 합류했는지 다음 로그 확인.

- [ ] **Step 4: `_scratch` 임시 파일 정리(선택) 및 `.env`에 임시로 넣은 송파 ID/비번 제거.**

---

## Self-Review 메모(작성자 점검)
- **Spec 커버리지:** 잠실 추가(Task 3·5) / 시간필터(Task 4) / 빈자리 요약 아침8시(Task 7·8) / 빈자리 없음 한 줄(Task 6) — 모두 task 있음.
- **회귀 보호:** 송파 파싱 회귀(Task 2) + 전체 pytest 매 task.
- **불확실성:** 잠실 HTML/로그인 동일 여부 → Task 1 실측, 다르면 Task 5에서 파서 조정 분기 명시.
- **타입 일관성:** `fetch_esongpa_slots`, `parse_esongpa`, `is_jamsil_wanted`, `format_summary`, `run_summary` 이름 전 task 일치.
