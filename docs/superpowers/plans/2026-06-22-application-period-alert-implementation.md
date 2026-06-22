# 신청기간 알림 기능 — 구현 공정표

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 포이·세곡의 신청 상태가 `준비중`→`접수중`으로 바뀌면 텔레그램으로 "신청 시작" 알림을 보낸다.

**Architecture:** 기존 빈자리 알림과 똑같은 패턴(조회→비교→알림→저장)을 시설 신청상태에 적용. 기존 5분 워크플로에 통합.

**Tech Stack:** Python, pytest, requests, 텔레그램 Bot API (기존과 동일)

> 설계서: `docs/superpowers/specs/2026-06-22-application-period-alert-design.md`

---

## 파일 변경 요약

| 파일 | 변경 |
|------|------|
| `src/config.py` | `FACILITIES` 목록 + `STATUS_PATH` 추가 |
| `src/fetcher.py` | `parse_status`, `fetch_facility_status` 추가 |
| `src/differ.py` | `find_opened`(준비중→접수중 감지) 추가 |
| `src/notifier.py` | `format_application_message` 추가 |
| `src/state.py` | `save_status`, `load_status` 추가 |
| `src/main.py` | 신청상태 알림 흐름 추가 |
| `.github/workflows/check.yml` | `status.json`도 캐시 |

---

## Task 1: 설정 + 신청상태 조회기

**Files:**
- Modify: `src/config.py`, `src/fetcher.py`
- Test: `tests/test_facility_status.py`

- [ ] **Step 1: config에 모니터링 대상 추가**

`src/config.py` 끝에 추가:
```python
# 신청기간 알림 대상 시설 (대표 코트 1개로 상태 확인 — 상태는 시설 단위라 코트별 동일)
FACILITIES = [
    {"name": "포이 테니스장", "comcd": "GNCC06", "part": "04", "place": "15"},
    {"name": "세곡 체육공원", "comcd": "GNCC33", "part": "04", "place": "13"},
]

# 시설 신청상태 직전 기록 파일
STATUS_PATH = "status.json"
```

- [ ] **Step 2: 실패하는 테스트 작성**

Create `tests/test_facility_status.py`:
```python
"""신청상태 파서 테스트: place_detail 응답에서 상태/접수기간/이용기간만 뽑아야 함."""
from src.fetcher import parse_status


def test_상태_필드_추출():
    detail = {
        "state_nm": "접수중",
        "receipt_period": "2026-06-24~2026-06-29",
        "period": "2026-07-01~2026-07-31",
        "confirm_type": "심의승인",
    }
    assert parse_status(detail) == {
        "state": "접수중",
        "receipt": "2026-06-24~2026-06-29",
        "period": "2026-07-01~2026-07-31",
    }


def test_빈_필드는_빈_문자열():
    assert parse_status({}) == {"state": "", "receipt": "", "period": ""}
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_facility_status.py -v`
Expected: FAIL — `cannot import name 'parse_status'`

- [ ] **Step 4: fetcher에 구현**

`src/fetcher.py`에 추가 (맨 위 import에 `from src.config import COURTS, OPEN_STATE_CODES, FACILITIES` 로 `FACILITIES` 추가):
```python
DETAIL_API = ROOT + "rest/facilities/place_detail"


def parse_status(detail):
    """place_detail 응답에서 신청 상태 정보만 추린다."""
    return {
        "state": detail.get("state_nm", ""),
        "receipt": detail.get("receipt_period", ""),
        "period": detail.get("period", ""),
    }


def fetch_facility_status():
    """포이·세곡의 신청 상태를 {시설명: {state, receipt, period}}로 돌려준다.

    한 시설 조회가 실패하면 그 시설만 건너뛴다(빈 dict 항목 없음).
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_facility_status.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/config.py src/fetcher.py tests/test_facility_status.py
git commit -m "feat: 신청상태 조회기(parse_status·fetch_facility_status) 추가"
```

---

## Task 2: 시설상태 저장/불러오기

**Files:**
- Modify: `src/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_state.py` 끝에 추가)**

```python
from src.state import save_status, load_status


def test_시설상태_저장_불러오기(tmp_path):
    path = tmp_path / "status.json"
    status = {"포이 테니스장": {"state": "준비중", "receipt": "6/24~6/29", "period": "-"}}
    save_status(path, status)
    assert load_status(path) == status


def test_없는_상태파일은_빈_dict(tmp_path):
    assert load_status(tmp_path / "none.json") == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL — `cannot import name 'save_status'`

- [ ] **Step 3: state.py에 구현 (파일 끝에 추가)**

```python
def save_status(path, status: dict) -> None:
    """시설별 신청상태 dict를 JSON으로 저장."""
    Path(path).write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")


def load_status(path) -> dict:
    """시설별 신청상태 dict를 불러옴. 파일이 없으면 빈 dict."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/state.py tests/test_state.py
git commit -m "feat: 시설 신청상태 저장/불러오기 추가"
```

---

## Task 3: 전환 감지 + 알림 메시지

**Files:**
- Modify: `src/differ.py`, `src/notifier.py`
- Test: `tests/test_differ.py`, `tests/test_notifier.py`

- [ ] **Step 1: 전환 감지 실패 테스트 (`tests/test_differ.py` 끝에 추가)**

```python
from src.differ import find_opened


def test_준비중에서_접수중_전환만_감지():
    previous = {
        "포이 테니스장": {"state": "준비중"},
        "세곡 체육공원": {"state": "접수중"},
    }
    current = {
        "포이 테니스장": {"state": "접수중"},   # 준비중→접수중 = 신청시작 → 포함
        "세곡 체육공원": {"state": "접수중"},   # 그대로 → 제외
    }
    assert find_opened(current, previous) == ["포이 테니스장"]


def test_직전_없으면_전환_아님():
    current = {"포이 테니스장": {"state": "접수중"}}
    assert find_opened(current, {}) == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_differ.py -v`
Expected: FAIL — `cannot import name 'find_opened'`

- [ ] **Step 3: differ.py에 구현 (파일 끝에 추가)**

```python
def find_opened(current: dict, previous: dict) -> list:
    """신청 상태가 '준비중' → '접수중'으로 바뀐 시설명 목록을 돌려준다.

    직전 기록이 없는 시설은 전환으로 보지 않는다(첫 실행 폭탄 방지).
    """
    opened = []
    for name, info in current.items():
        prev_state = previous.get(name, {}).get("state")
        if prev_state == "준비중" and info.get("state") == "접수중":
            opened.append(name)
    return opened
```

- [ ] **Step 4: 알림 메시지 실패 테스트 (`tests/test_notifier.py` 끝에 추가)**

```python
from src.notifier import format_application_message


def test_신청시작_메시지():
    info = {"state": "접수중", "receipt": "2026-06-24~2026-06-29", "period": "2026-07-01~2026-07-31"}
    msg = format_application_message("포이 테니스장", info)
    assert "포이 테니스장" in msg
    assert "신청 시작" in msg
    assert "2026-06-24~2026-06-29" in msg
```

- [ ] **Step 5: notifier.py에 구현 (파일 끝에 추가)**

```python
def format_application_message(name: str, info: dict) -> str:
    """신청 시작 알림 메시지를 만든다."""
    return (
        f"🎾 {name} 신청 시작!\n"
        f"📋 접수기간: {info.get('receipt', '')}\n"
        f"📅 이용: {info.get('period', '')}\n"
        f"👉 지금 신청: {RESERVE_URL}"
    )
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_differ.py tests/test_notifier.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add src/differ.py src/notifier.py tests/test_differ.py tests/test_notifier.py
git commit -m "feat: 신청 준비중→접수중 전환 감지 + 신청시작 메시지"
```

---

## Task 4: main 통합 + 워크플로 캐시

**Files:**
- Modify: `src/main.py`, `.github/workflows/check.yml`

- [ ] **Step 1: main.py에 신청상태 알림 추가**

`src/main.py`를 아래로 교체 (기존 빈자리 흐름 + 신청상태 흐름):
```python
"""전체 흐름 조율: ①빈자리 알림 ②신청기간 알림."""
import sys
from pathlib import Path

from src.fetcher import fetch_slots, fetch_facility_status
from src.filters import is_wanted_time
from src.differ import find_new_slots, find_opened
from src.notifier import format_message, send_telegram, format_application_message
from src.state import load_slots, save_slots, load_status, save_status
from src.config import STATUS_PATH

STATE_PATH = "state.json"  # 직전 빈자리 기록


def run_vacancy_alert():
    """① 빈자리/취소표 알림."""
    try:
        current_all = fetch_slots()
    except Exception as e:
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        print(f"[읽기 실패] {e}")
        return
    wanted = [s for s in current_all if is_wanted_time(s)]
    is_first = not Path(STATE_PATH).exists()
    new_slots = find_new_slots(wanted, load_slots(STATE_PATH))
    if is_first:
        print(f"[빈자리 첫 실행] {len(wanted)}건 기준 저장(알림 생략)")
    else:
        msg = format_message(new_slots)
        if msg:
            send_telegram(msg)
            print(f"[빈자리 알림] {len(new_slots)}건")
        else:
            print("[빈자리 변화 없음]")
    save_slots(STATE_PATH, wanted)


def run_application_alert():
    """② 신청기간(준비중→접수중) 알림."""
    status = fetch_facility_status()
    if not status:
        print("[신청상태 조회 0건]")
        return
    is_first = not Path(STATUS_PATH).exists()
    opened = find_opened(status, load_status(STATUS_PATH))
    if is_first:
        print(f"[신청상태 첫 실행] {len(status)}곳 기준 저장(알림 생략)")
    else:
        for name in opened:
            send_telegram(format_application_message(name, status[name]))
            print(f"[신청 시작 알림] {name}")
        if not opened:
            print("[신청상태 변화 없음]")
    save_status(STATUS_PATH, status)


def main() -> int:
    run_vacancy_alert()
    run_application_alert()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 전체 테스트 확인**

Run: `python -m pytest -q`
Expected: 모든 테스트 PASS

- [ ] **Step 3: check.yml 캐시에 status.json 추가**

`.github/workflows/check.yml`의 "직전 기록 복원" 단계 `path`를 수정:
```yaml
      - name: 직전 기록 복원
        uses: actions/cache@v4
        with:
          path: |
            state.json
            status.json
          key: tennis-state-v3-${{ github.run_id }}
          restore-keys: tennis-state-v3-
```
(key를 v3로 올려 신청상태 포함 새 출발)

- [ ] **Step 4: 로컬 실행 확인 (.env에 토큰 있는 상태)**

Run: `python -m src.main`
Expected: `[빈자리 …]` 와 `[신청상태 첫 실행 …]` 두 줄 출력, `status.json` 생성

- [ ] **Step 5: 커밋**

```bash
git add src/main.py .github/workflows/check.yml
git commit -m "feat: main에 신청기간 알림 통합 + status.json 캐시"
```

---

## Task 5: 배포 검증

- [ ] **Step 1: 전체 테스트 + 실제 조회**

Run: `python -m pytest -q && python -c "from src.fetcher import fetch_facility_status; print(fetch_facility_status())"`
Expected: 테스트 전부 PASS + 포이/세곡 상태 출력 (예: 포이=준비중, 세곡=접수중)

- [ ] **Step 2: push + 워크플로 재실행 (사용자 승인 후)**

```bash
git push
gh workflow run check.yml --repo ponyo413/gangnam-tennis-alert
```

- [ ] **Step 3: 첫 실행 성공 확인 후 사용자 보고**

---

## Self-Review

**1. 스펙 커버리지:** 대상 시설(FACILITIES Task1)·전환감지(find_opened Task3)·메시지(Task3)·통합(Task4)·캐시(Task4)·첫실행 가드(Task4 run_application_alert) — 전부 커버 ✅

**2. 빈칸 점검:** 모든 코드 완성형, 자리표시 없음 ✅

**3. 타입 일관성:** `parse_status`→`{state,receipt,period}` dict, `fetch_facility_status`→`{name: 그 dict}`, `find_opened(current,previous)`→`[name]`, `format_application_message(name,info)`, `save_status/load_status(path,...)` — 전 Task 일치 ✅
