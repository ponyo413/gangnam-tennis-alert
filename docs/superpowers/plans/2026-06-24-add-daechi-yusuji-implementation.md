# 대치유수지 테니스장 추가 — 구현 공정표 (개정: 15분·08~24시 저빈도)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대치유수지 테니스장 빈자리(취소표)를 강남·송파·잠실과 같은 텔레그램 봇에서 함께 알린다. 단 사이트의 "매크로 빈번 접속 금지" 공지를 존중해 **15분 간격 + 한국시간 08~24시에만** 조회한다.

**Architecture:** 로그인 없는 HTML 페이지라 전용 부품 `src/daechi.py`를 신설(파싱 `parse_daechi` + 조회 `fetch_daechi_slots` + 게이트 `is_daechi_due`). 봇은 5분마다 돌지만 `main`이 게이트로 "지금 접속할 때인가"를 판단해 **15분에 1번만 실제 접속**하고, 그 외엔 **직전 박제 결과를 유지**한다. 마지막 조회 시각은 `state.py`에 저장한다.

**Tech Stack:** Python 3, `requests`(+`http_session.make_session`), 표준 `re`/`datetime`, pytest(monkeypatch, tmp_path).

설계서: `docs/superpowers/specs/2026-06-24-add-daechi-yusuji-design.md`

---

## 파일 구조

| 파일 | 책임 | 작업 |
|------|------|------|
| `src/daechi.py` | 대치유수지 조회 + 파싱 + 조회 게이트 | **신규** |
| `tests/test_daechi.py` | 파싱·조회·게이트 동작 박제 | **신규** |
| `src/state.py` | 마지막 조회 시각 저장/로드 함수 추가 | 함수 2개 추가 |
| `tests/test_state.py` | 시각 저장 왕복 테스트 | 테스트 2개 추가 |
| `settings.yaml` | 대치유수지 감시 시간대 | 블록 추가 |
| `src/main.py` | 게이트로 조회 or 직전 유지 + 합류 | import·상수·호출 |
| `README.md` | 감시 대상 목록 | 한 줄 |

> 빈자리 칸 구조(실측): 한 `<dl>`(시간대 행) 안에 `<dt>` 3개 = A·B·C 코트.
> `가능` 칸만 `data-date="YYYY-MM-DD" data-time="N"`을 가짐. 시작시각 = `7 + N*2` (0→07시 … 6→19시).

> **저빈도 규칙:** 실제 접속 = (KST 08~23시) **그리고** (마지막 조회 후 15분 경과). 둘 중 하나라도
> 아니면 접속하지 않고 직전 박제 빈자리를 그대로 쓴다. 빈도/시간창은 코드 상수.

> **실행 위치:** 아래 모든 `python`·`pytest`·`git` 명령은 봇 루트
> `C:\Users\user\Desktop\gangnam-tennis-alert`에서 실행한다(`src` 패키지 import가 되도록).

---

## Task 1: `parse_daechi` — 빈자리 칸 파싱  ✅ 이미 완료 (커밋 `9f15347`)

> 이 Task는 개정 전 이미 구현·검토 완료. 파싱은 조회 빈도와 무관하므로 **변경 없이 유효**.
> 참고용 최종 코드(이미 반영됨):

`src/daechi.py` (현재 상태):
```python
# src/daechi.py
"""대치유수지 테니스장 빈자리 조회 — 로그인 없는 HTML 파싱(전용 부품).

강남(REST)·esongpa(로그인)와 사이트 방식이 달라 따로 둔다.
빈자리(possible_icn_on) 칸의 data-date/data-time과 <dt> 순서(A·B·C)로 슬롯을 만든다.
시간대/켜고끄기는 settings.yaml(설정표)에서 받아 is_wanted_for로 거른다.
"""
import re

from src.models import Slot

CENTER = "대치유수지"             # Slot.court(시설명)에 들어갈 이름
COURTS = ["A코트", "B코트", "C코트"]  # 한 행 <dt> 순서 = 코트 순서

_ROW_RE = re.compile(r"<dl>(.*?)</dl>", re.DOTALL)
_CELL_RE = re.compile(r"<dt>(.*?)</dt>", re.DOTALL)
_DATE_RE = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})"')
_TIME_RE = re.compile(r'data-time="(\d+)"')


def parse_daechi(html):
    """HTML에서 '가능'(빈자리) 칸만 Slot 목록으로. 시작시각 = 7 + data-time*2."""
    slots = []
    for row in _ROW_RE.findall(html):
        for idx, cell in enumerate(_CELL_RE.findall(row)[:3]):  # 1·2·3 = A·B·C
            if "possible_icn_on" not in cell:
                continue
            dm, tm = _DATE_RE.search(cell), _TIME_RE.search(cell)
            if not (dm and tm):
                continue
            hour = 7 + int(tm.group(1)) * 2
            slots.append(Slot(CENTER, COURTS[idx], dm.group(1), f"{hour:02d}:00"))
    return slots
```

- [x] 완료 — 테스트 2건 통과, 커밋 `9f15347`.

---

## Task 2: `fetch_daechi_slots` — 조회 + 시간/미래 필터 (순수 조회)

> 이 함수는 **게이트를 모른다**(호출 빈도는 Task 5의 main이 통제). 순수 조회만.

**Files:**
- Modify: `src/daechi.py` (상수·함수 추가)
- Modify: `tests/test_daechi.py` (테스트 추가)

- [ ] **Step 1: Write the failing test**

`tests/test_daechi.py` 끝에 추가:
```python
from src.daechi import fetch_daechi_slots


def test_fetch_skips_when_disabled():
    """받기=False거나 설정이 없으면 조회 자체를 안 하고 빈 목록."""
    assert fetch_daechi_slots({"대치유수지": {"받기": False}}) == []
    assert fetch_daechi_slots({}) == []


def test_fetch_filters_time_and_drops_past(monkeypatch):
    """원하는 시각(매일 [7])만 + 미래만 남긴다. 과거·다른시각은 제외."""
    html = (
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2000-01-01\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        "<dl><dd>09:00~11:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"1\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
    )

    class FakeResp:
        text = html

    monkeypatch.setattr("requests.Session.get", lambda self, *a, **k: FakeResp())
    monkeypatch.setattr("src.daechi._months", lambda today: [(2099, 7)])

    settings = {"대치유수지": {"받기": True, "매일": [7]}}
    slots = fetch_daechi_slots(settings)

    assert len(slots) == 1
    assert slots[0].date == "2099-07-04"
    assert slots[0].time == "07:00"
    assert slots[0].place == "A코트"


def test_fetch_does_not_raise_on_network_error(monkeypatch):
    """조회가 터져도 예외를 밖으로 던지지 않고 빈 목록(다른 시설 알림 보호)."""
    def boom(self, *a, **k):
        raise RuntimeError("연결 실패")

    monkeypatch.setattr("requests.Session.get", boom)
    settings = {"대치유수지": {"받기": True, "매일": [7]}}
    assert fetch_daechi_slots(settings) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_daechi_slots'`

- [ ] **Step 3: Write minimal implementation**

`src/daechi.py` 상단 import에 추가:
```python
from datetime import datetime, timezone, timedelta

from src.filters import is_wanted_for
from src.http_session import make_session
```

`src/daechi.py`의 상수 영역(`COURTS` 아래)에 추가:
```python
KST = timezone(timedelta(hours=9))  # GitHub Actions는 UTC라 한국시각 고정
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
BASE = "https://www.xn--vk1b79znxd34c61h.kr/"  # 대치유수지.kr(퓨니코드)
TENNIS_TYPE = "8"  # type=8 = 테니스장(7=축구장 등 다른 종목)
```

`src/daechi.py` 끝(`parse_daechi` 아래)에 추가:
```python
def _months(today):
    """이번 달·다음 달 (연, 월) 두 개 — 페이지를 두 달치 조회하기 위함."""
    if today.month == 12:
        nxt = (today.year + 1, 1)
    else:
        nxt = (today.year, today.month + 1)
    return [(today.year, today.month), nxt]


def fetch_daechi_slots(settings):
    """대치유수지 빈자리(설정 기반 켜고끄기 + 시간/미래 필터)를 Slot 목록으로.

    settings: {"대치유수지": {받기, 평일/토/…}} 형태(설정표). 받기=False면 건너뜀.
    한 달 조회가 실패해도 다른 달은 계속(시설 전체가 죽지 않게).
    호출 빈도(15분·08~24시)는 이 함수가 아니라 main의 게이트가 통제한다.
    """
    cfg = settings.get(CENTER)
    if not cfg or not cfg.get("받기"):
        return []  # 설정표에서 끈 시설은 조회 안 함

    now = datetime.now(KST)
    session = make_session(HEADERS)
    result = []
    for year, month in _months(now.date()):
        try:
            r = session.get(BASE, params={
                "act": "reservation.reservation_list",
                "type": TENNIS_TYPE,
                "cyear": year,
                "cmonth": month,
            }, timeout=20)
            for slot in parse_daechi(r.text):
                slot_dt = datetime.strptime(slot.date + slot.time,
                                            "%Y-%m-%d%H:%M").replace(tzinfo=KST)
                if slot_dt > now and is_wanted_for(slot, cfg):
                    result.append(slot)
        except Exception as ex:  # 한 달 실패는 건너뛰고 계속
            print(f"[대치유수지 {year}-{month:02d} 조회 실패] {ex}")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: PASS (5 passed — Task 1의 2건 + 이번 3건)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add src/daechi.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 조회+시간/미래 필터(fetch_daechi_slots) 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `is_daechi_due` — 조회 게이트(15분 + 08~24시)

순수함수. "지금 대치유수지를 실제로 접속할 때인가?"만 판정한다.

**Files:**
- Modify: `src/daechi.py` (상수·함수 추가)
- Modify: `tests/test_daechi.py` (테스트 추가)

- [ ] **Step 1: Write the failing test**

`tests/test_daechi.py` 끝에 추가:
```python
from datetime import datetime, timezone, timedelta
from src.daechi import is_daechi_due

_KST = timezone(timedelta(hours=9))


def _at(h, mi=0):
    """그 날 KST h시 mi분(테스트용 고정 시각)."""
    return datetime(2026, 6, 24, h, mi, tzinfo=_KST)


def test_due_dawn_is_false():
    """새벽(03시)은 활동시간(08~24시) 밖 → 조회 안 함."""
    assert is_daechi_due(_at(3), None) is False


def test_due_midnight_is_false():
    """자정(00시)도 활동시간 밖 → 조회 안 함."""
    assert is_daechi_due(_at(0), None) is False


def test_due_first_time_in_active_hours():
    """활동시간(08시) + 첫 조회(last=None) → 조회."""
    assert is_daechi_due(_at(8), None) is True


def test_due_within_interval_is_false():
    """활동시간이지만 마지막 조회 후 10분(15분 미만) → 조회 안 함."""
    assert is_daechi_due(_at(8, 10), _at(8, 0)) is False


def test_due_after_interval_is_true():
    """마지막 조회 후 20분(15분 경과) → 조회."""
    assert is_daechi_due(_at(8, 20), _at(8, 0)) is True


def test_due_late_evening_is_true():
    """23시는 아직 활동시간 안 → (첫 조회) 조회."""
    assert is_daechi_due(_at(23), None) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_daechi_due'`

- [ ] **Step 3: Write minimal implementation**

`src/daechi.py`의 상수 영역(Task 2에서 만든 `TENNIS_TYPE` 아래)에 추가 — **`KST`는 Task 2에서 이미 정의했으니 재정의하지 말 것**:
```python
# 조회 게이트(매크로 빈번접속 공지 존중) — 빈도/활동시간은 코드 상수로 고정
ACTIVE_START_HOUR = 8    # 조회 시작 시각(08시)
ACTIVE_END_HOUR = 24     # 조회 끝(24시=자정) → now.hour < 24라 실질 08~23시
FETCH_INTERVAL_MIN = 15  # 조회 최소 간격(분)
```

`src/daechi.py` 끝(`fetch_daechi_slots` 아래)에 추가:
```python
def is_daechi_due(now, last_fetch, interval_min=FETCH_INTERVAL_MIN):
    """지금 대치유수지를 실제로 조회할 때인지 판정(순수함수).

    실제 접속 조건 = ① 활동시간(KST 08~24시) 안 AND ② 마지막 조회 후 interval_min분 경과.
    - 활동시간 밖(새벽 0~8시) → False (접속 안 함, 사이트 부담·공지 존중)
    - 한 번도 조회 안 했으면(last_fetch=None) 활동시간 안일 때 True
    now: KST aware datetime. last_fetch: datetime 또는 None.
    """
    if not (ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR):
        return False
    if last_fetch is None:
        return True
    return (now - last_fetch).total_seconds() >= interval_min * 60
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: PASS (11 passed — 누적 5건 + 이번 6건)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add src/daechi.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 조회 게이트 is_daechi_due(15분+08~24시) 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 마지막 조회 시각 저장/로드 (`state.py`)

**Files:**
- Modify: `src/state.py` (함수 2개 추가)
- Modify: `tests/test_state.py` (테스트 2개 추가)

- [ ] **Step 1: Write the failing test**

`tests/test_state.py` 끝에 추가:
```python
def test_대치유수지_조회시각_저장_불러오기(tmp_path):
    """마지막 조회 시각(ISO 문자열)을 저장하고 그대로 다시 읽어야 함."""
    from src.state import save_daechi_fetch_time, load_daechi_fetch_time
    path = tmp_path / "daechi_fetch.json"
    save_daechi_fetch_time(path, "2026-06-24T14:30:00+09:00")
    assert load_daechi_fetch_time(path) == "2026-06-24T14:30:00+09:00"


def test_없는_조회시각파일은_None(tmp_path):
    """파일이 없으면(첫 실행) None — 아직 한 번도 조회 안 한 것으로 취급."""
    from src.state import load_daechi_fetch_time
    assert load_daechi_fetch_time(tmp_path / "none.json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'save_daechi_fetch_time'`

- [ ] **Step 3: Write minimal implementation**

`src/state.py` 끝에 추가:
```python
def load_daechi_fetch_time(path):
    """대치유수지 마지막 조회 시각(ISO 문자열). 파일이 없거나 깨졌으면 None(아직 조회 안 함)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("at")
    except Exception:
        return None


def save_daechi_fetch_time(path, iso_str) -> None:
    """대치유수지 마지막 조회 시각(ISO 문자열)을 저장."""
    Path(path).write_text(json.dumps({"at": iso_str}, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS (기존 6건 + 이번 2건)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add src/state.py tests/test_state.py
git -C "$REPO" commit -m "feat(daechi): 마지막 조회 시각 저장/로드(state) 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 설정표 등록 + main 배선(게이트로 조회 or 직전 유지)

**Files:**
- Modify: `settings.yaml` (블록 추가)
- Modify: `src/main.py` (import·상수·호출)
- Modify: `tests/test_daechi.py` (설정/배선 확인 테스트)

- [ ] **Step 1: Write the failing test**

`tests/test_daechi.py` 끝에 추가:
```python
def test_settings_has_daechi_block():
    """설정표(settings.yaml)에 대치유수지가 정상 형식으로 들어있다."""
    from src.settings_loader import load_settings
    settings, err = load_settings()
    assert err is None
    assert settings["대치유수지"]["받기"] is True
    assert settings["대치유수지"]["평일"] == [19]
    assert settings["대치유수지"]["토"] == [7, 9, 19]


def test_main_wires_daechi():
    """main이 대치유수지 부품(조회·게이트)을 가져다 쓴다(배선 확인)."""
    import src.main as m
    assert hasattr(m, "fetch_daechi_slots")
    assert hasattr(m, "is_daechi_due")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daechi.py::test_settings_has_daechi_block tests/test_daechi.py::test_main_wires_daechi -v`
Expected: FAIL — `KeyError: '대치유수지'` / `AttributeError: ... 'is_daechi_due'`

- [ ] **Step 3a: `settings.yaml` 끝에 블록 추가**

```yaml

대치유수지:                  # 2시간 단위(07~09 … 19~21), 로그인 없음. 조회는 15분·08~24시(코드 상수)
  받기: true               # 끄려면 false 로만 바꾸면 끝
  평일: [19]               # 월~금: 저녁 7시(19~21)
  토: [7, 9, 19]           # 토요일: 오전 7·9시 + 저녁 7시
  # 일요일은 줄 없음 = 감시 안 함
```

- [ ] **Step 3b: `src/main.py` import·상수 추가**

`from src.esongpa import fetch_esongpa_slots` 아래에:
```python
from src.daechi import fetch_daechi_slots, is_daechi_due, KST
```

기존 `from src.state import (...)`에 `save_daechi_fetch_time, load_daechi_fetch_time`를 추가하고, 파일 상단에 `from datetime import datetime`을 추가(이미 없으면).

상수 영역(`READ_FAIL_PATH` 부근)에 추가:
```python
DAECHI_SLOTS_PATH = "daechi_slots.json"   # 대치유수지 직전 빈자리(박제)
DAECHI_TIME_PATH = "daechi_fetch.json"    # 대치유수지 마지막 조회 시각
```

- [ ] **Step 3c: `run_vacancy_alert()`에 게이트 블록 추가**

`save_failures(FAIL_PATH, failures)` **바로 위**(esongpa try/except 다음)에 삽입:
```python
    # 대치유수지 — 15분 간격 + 08~24시에만 실제 접속(매크로 빈번접속 공지 존중).
    # 그 외 실행에선 직전에 박제한 빈자리를 그대로 유지(가짜 변동 알림 방지).
    now = datetime.now(KST)
    last_str = load_daechi_fetch_time(DAECHI_TIME_PATH)
    last_dt = datetime.fromisoformat(last_str) if last_str else None
    if is_daechi_due(now, last_dt):
        try:
            daechi_slots = fetch_daechi_slots(settings)
            save_slots(DAECHI_SLOTS_PATH, daechi_slots)            # 결과 박제
            save_daechi_fetch_time(DAECHI_TIME_PATH, now.isoformat())
            wanted += daechi_slots
        except Exception as e:
            failures["대치유수지"] = failures.get("대치유수지", 0) + 1
            wanted += load_slots(DAECHI_SLOTS_PATH)                # 실패 시 직전 유지
            print(f"[대치유수지 조회 실패] {e}")
    else:
        wanted += load_slots(DAECHI_SLOTS_PATH)                    # 시간창 밖/15분 미경과 → 직전 유지
```

- [ ] **Step 3d: `run_summary()`에 직전 결과 합류 추가**

`run_summary()`의 esongpa try/except 다음, `failures = load_failures(FAIL_PATH)` **위**에 삽입(요약은 새로 접속하지 않고 박제본만 사용):
```python
    wanted += load_slots(DAECHI_SLOTS_PATH)   # 대치유수지: 직전 박제 빈자리(요약은 접속 안 함)
```

- [ ] **Step 4: Run tests (대상 + 전체)**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: PASS (13 passed)

Run: `python -m pytest -q`
Expected: 기존 + 신규 전부 PASS (실패 0). `python -c "import src.main"`도 오류 없어야 함.

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add settings.yaml src/main.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 설정표 등록 + main 게이트 배선(조회 or 직전유지)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 실측 검증 + README

**Files:**
- Modify: `README.md`
- (검증 — 네트워크는 최소 1회만)

- [ ] **Step 1: 저장된 실측 HTML로 파싱 검증 (네트워크 0)**

조사 때 저장해 둔 실측 페이지로 `parse_daechi`가 빈자리를 뽑는지 확인(접속 안 함):
```bash
python -c "import tempfile, os; from src.daechi import parse_daechi; \
html=open(os.path.join(tempfile.gettempdir(),'daechi.html'),encoding='utf-8').read(); \
s=parse_daechi(html); print('파싱 빈자리', len(s), '건'); \
[print(x.place, x.date, x.time) for x in s[:10]]"
```
Expected: `파싱 빈자리 N 건`과 A/B/C코트·날짜·시각 출력. **19시(`19:00`)가 한 건이라도 있으면 `data-time=6` 매핑 실증.** (저장본이 없으면 이 단계는 건너뛰고 Step 2로.)

- [ ] **Step 2: 실제 조회 1회만 동작 확인 (네트워크 1회)**

게이트를 거치지 않고 `fetch_daechi_slots`를 직접 1회 호출(공지 존중: 검증은 1회만):
```bash
python -c "from src.daechi import fetch_daechi_slots; from src.settings_loader import load_settings; \
st,_=load_settings(); s=fetch_daechi_slots(st); \
print('설정대로 빈자리', len(s), '건'); \
[print(x.place, x.date, x.time) for x in s[:10]]"
```
Expected: 오류 없이 출력. 나오는 시각이 모두 19시(평일) 또는 7·9·19시(토)이고 일요일은 없는지 눈으로 확인. 0건이어도 오류 없이 끝나면 정상.

- [ ] **Step 3: `README.md` 감시 대상에 추가**

`- 감시 대상: 포이 테니스장, 강남세곡체육공원 테니스장` 줄을 아래로 교체:
```markdown
- 감시 대상: 포이·강남세곡 테니스장, 송파·잠실(유수지) 테니스장, 대치유수지 테니스장
- 대치유수지: 사이트 공지(매크로 제한)에 따라 15분 간격·한국시간 08~24시에만 조회
```

- [ ] **Step 4: 전체 테스트 최종 확인**

Run: `python -m pytest -q`
Expected: 전부 PASS(실패 0)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add README.md
git -C "$REPO" commit -m "docs(daechi): README 감시 대상+저빈도 안내 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 완료 기준(Definition of Done)

- [ ] `python -m pytest -q` 전부 통과(신규 포함)
- [ ] `parse_daechi`가 실측 HTML에서 19시(`data-time=6`)까지 정확히 추출
- [ ] `is_daechi_due`가 새벽 False / 08~23시 True / 15분 미경과 False로 동작
- [ ] main이 게이트로 "조회 or 직전 유지"를 분기(접속은 15분·08~24시에만)
- [ ] 기존 부품(`fetcher.py`·`esongpa.py`·`filters.py`·`notifier.py`) 무수정
- [ ] (배포는 별도) GitHub push 전 사용자 승인 — push해야 실제 가동

## 후속(이번 범위 밖)
- 알림 끝 예약 링크는 강남 1개 공용 유지(시설별 링크는 추후).
- 빈도/시간창을 settings.yaml로 빼는 것은 YAGNI(지금은 코드 상수로 충분).
