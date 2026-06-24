# 대치유수지 테니스장 추가 — 구현 공정표

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대치유수지 테니스장 빈자리(취소표)를 강남·송파·잠실과 같은 텔레그램 봇에서 함께 알린다.

**Architecture:** 로그인 없는 Rhymix 계열 HTML 페이지라, 강남(REST)·esongpa(로그인)와 별개의 전용 부품 `src/daechi.py`를 신설한다. 빈자리(`possible_icn_on`) 칸의 `data-date`·`data-time`과 `<dt>` 순서(A·B·C)로 슬롯을 뽑고, 공용 `is_wanted_for`로 시간대를 거른다. 기존 부품은 손대지 않고 `main.py`에 호출 한 줄씩만 더한다.

**Tech Stack:** Python 3, `requests`(+`http_session.make_session`), 표준 `re`, pytest(monkeypatch).

설계서: `docs/superpowers/specs/2026-06-24-add-daechi-yusuji-design.md`

---

## 파일 구조

| 파일 | 책임 | 작업 |
|------|------|------|
| `src/daechi.py` | 대치유수지 조회 + 빈자리 파싱 + 시간/미래 필터 | **신규** (~70줄) |
| `tests/test_daechi.py` | 파싱·조회 동작 박제 | **신규** |
| `settings.yaml` | 대치유수지 감시 시간대 설정 | 블록 추가 |
| `src/main.py` | 빈자리/요약 흐름에 대치유수지 합류 | import + 호출 2곳 |
| `README.md` | 감시 대상 목록에 대치유수지 추가 | 한 줄 |

> 빈자리 칸 구조(실측): 한 `<dl>`(시간대 행) 안에 `<dt>` 3개 = A·B·C 코트.
> `가능` 칸만 `data-date="YYYY-MM-DD" data-time="N"`을 가짐. 시작시각 = `7 + N*2` (0→07시 … 6→19시).

> **실행 위치:** 아래 모든 `python`·`pytest`·`git` 명령은 봇 루트
> `C:\Users\user\Desktop\gangnam-tennis-alert`에서 실행한다(`src` 패키지 import가 되도록).

---

## Task 1: `parse_daechi` — 빈자리 칸 파싱

**Files:**
- Create: `src/daechi.py`
- Test: `tests/test_daechi.py`

- [ ] **Step 1: Write the failing test**

`tests/test_daechi.py`:
```python
# tests/test_daechi.py
"""대치유수지 파싱·조회 동작 박제 — 고정 HTML + 네트워크 monkeypatch."""
from src.daechi import parse_daechi

# 실측 구조 축약: 한 <dl>=한 시간대 행, <dt> 3개=A·B·C 코트.
# '가능'(possible_icn_on) 칸만 data-date/data-time을 가진다.
SAMPLE_HTML = (
    "<dl><dd>07:00~09:00</dd>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\" data-date=\"2099-07-04\" data-time=\"0\" data-type=\"9\">"
    "<img src=\"/images/sub/possible_icn_on.gif\" title=\"가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "</dl>"
    "<dl><dd>19:00~21:00</dd>"
    "<dt><a href=\"#\" class=\"_rev\" data-date=\"2099-07-04\" data-time=\"6\" data-type=\"9\">"
    "<img src=\"/images/sub/possible_icn_on.gif\" title=\"가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "</dl>"
)


def test_parse_extracts_only_available_with_court_and_time():
    """가능 칸만 추출 + 코트(순서)·시각(7+N*2) 매핑."""
    slots = parse_daechi(SAMPLE_HTML)
    # 07시 행: 2번째 칸(B코트) 가능 / 19시 행: 1번째 칸(A코트) 가능 → 2건
    assert len(slots) == 2
    by_time = {s.time: s for s in slots}

    s07 = by_time["07:00"]
    assert s07.court == "대치유수지"   # 시설명
    assert s07.place == "B코트"        # <dt> 2번째 = B
    assert s07.date == "2099-07-04"

    s19 = by_time["19:00"]
    assert s19.place == "A코트"        # <dt> 1번째 = A
    assert s19.date == "2099-07-04"


def test_parse_ignores_full_rows():
    """모든 칸이 '불가능'인 행은 0건."""
    full = (
        "<dl><dd>13:00~15:00</dd>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "</dl>"
    )
    assert parse_daechi(full) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_daechi' from 'src.daechi'` (또는 모듈 없음)

- [ ] **Step 3: Write minimal implementation**

`src/daechi.py`:
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

# 한 시간대 행(<dl>) → 그 안의 코트 칸(<dt>) → 빈자리 단서(data-date/time + on)
_ROW_RE = re.compile(r"<dl>(.*?)</dl>", re.DOTALL)
_CELL_RE = re.compile(r"<dt>(.*?)</dt>", re.DOTALL)
_DATE_RE = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})"')
_TIME_RE = re.compile(r'data-time="(\d+)"')


def parse_daechi(html):
    """HTML에서 '가능'(빈자리) 칸만 Slot 목록으로.

    각 <dl>(한 시간대 행)의 <dt> 1·2·3번째를 A·B·C 코트로 본다.
    'possible_icn_on'이면서 data-date/data-time이 있는 칸만 빈자리로 뽑는다.
    시작시각 = 7 + data-time*2 (0→07시 … 6→19시).
    """
    slots = []
    for row in _ROW_RE.findall(html):
        for idx, cell in enumerate(_CELL_RE.findall(row)[:3]):  # 1·2·3 = A·B·C
            if "possible_icn_on" not in cell:
                continue  # 불가능(찬) 칸 → 건너뜀
            dm, tm = _DATE_RE.search(cell), _TIME_RE.search(cell)
            if not (dm and tm):
                continue  # 날짜/시간 꼬리표 없으면 빈자리로 안 봄(안전)
            hour = 7 + int(tm.group(1)) * 2
            slots.append(Slot(CENTER, COURTS[idx], dm.group(1), f"{hour:02d}:00"))
    return slots
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add src/daechi.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 빈자리 칸 파싱(parse_daechi) 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `fetch_daechi_slots` — 조회 + 시간/미래 필터

**Files:**
- Modify: `src/daechi.py` (함수·상수 추가)
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
        # 미래 07시(가능) — 통과 대상
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        # 과거 07시(가능) — 미래 필터로 제외
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2000-01-01\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        # 미래 09시(가능) — 시간 필터(매일 [7])로 제외
        "<dl><dd>09:00~11:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"1\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
    )

    class FakeResp:
        text = html

    # 네트워크 차단: get은 항상 위 HTML. 달 루프 1회만(중복 방지) 돌도록 _months 고정.
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
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add src/daechi.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 조회+시간/미래 필터(fetch_daechi_slots) 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 설정표 등록 + main 배선

**Files:**
- Modify: `settings.yaml` (블록 추가)
- Modify: `src/main.py` (import + 호출 2곳)
- Modify: `tests/test_daechi.py` (설정/배선 확인 테스트)

- [ ] **Step 1: Write the failing test**

`tests/test_daechi.py` 끝에 추가:
```python
def test_settings_has_daechi_block():
    """설정표(settings.yaml)에 대치유수지가 정상 형식으로 들어있다."""
    from src.settings_loader import load_settings
    settings, err = load_settings()
    assert err is None                       # 형식 오류 없음
    assert settings["대치유수지"]["받기"] is True
    assert settings["대치유수지"]["평일"] == [19]
    assert settings["대치유수지"]["토"] == [7, 9, 19]


def test_main_wires_daechi():
    """main이 대치유수지 부품을 가져다 쓴다(배선 확인)."""
    import src.main as m
    assert hasattr(m, "fetch_daechi_slots")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daechi.py::test_settings_has_daechi_block tests/test_daechi.py::test_main_wires_daechi -v`
Expected: FAIL — `KeyError: '대치유수지'` (설정 없음) / `AttributeError: ... 'fetch_daechi_slots'` (main 미배선)

- [ ] **Step 3a: `settings.yaml` 끝에 블록 추가**

```yaml

대치유수지:                  # 2시간 단위(07~09 … 19~21), 로그인 없음
  받기: true               # 끄려면 false 로만 바꾸면 끝
  평일: [19]               # 월~금: 저녁 7시(19~21)
  토: [7, 9, 19]           # 토요일: 오전 7·9시 + 저녁 7시
  # 일요일은 줄 없음 = 감시 안 함
```

- [ ] **Step 3b: `src/main.py` import 추가**

`from src.esongpa import fetch_esongpa_slots` 아래 줄에:
```python
from src.daechi import fetch_daechi_slots
```

- [ ] **Step 3c: `run_vacancy_alert()`에 호출 추가**

`save_failures(FAIL_PATH, failures)` **바로 위**(esongpa try/except 다음)에 삽입:
```python
    # 대치유수지(로그인 없음) — 실패해도 다른 시설 알림은 계속 + 실패 누적
    try:
        wanted += fetch_daechi_slots(settings)
    except Exception as e:
        failures["대치유수지"] = failures.get("대치유수지", 0) + 1
        print(f"[대치유수지 조회 실패] {e}")
```

- [ ] **Step 3d: `run_summary()`에 호출 추가**

`run_summary()`의 esongpa try/except 다음, `failures = load_failures(FAIL_PATH)` **위**에 삽입:
```python
    try:
        wanted += fetch_daechi_slots(settings)   # 대치유수지(요약에도 합류)
    except Exception as e:
        print(f"[요약-대치유수지 조회 실패] {e}")
```

- [ ] **Step 4: Run tests (대상 + 전체)**

Run: `python -m pytest tests/test_daechi.py -v`
Expected: PASS (7 passed)

Run: `python -m pytest -q`
Expected: 기존 테스트 전부 PASS + 신규 7건 PASS (실패 0)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add settings.yaml src/main.py tests/test_daechi.py
git -C "$REPO" commit -m "feat(daechi): 설정표 등록 + main 빈자리/요약 흐름에 합류" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 실제 조회 검증 + README

**Files:**
- Modify: `README.md`
- (검증 전용, 코드 변경 없음 — 실제 사이트 1회 조회)

- [ ] **Step 1: 실제 사이트 파싱 검증 (네트워크)**

Run:
```bash
cd "C:/Users/user/Desktop/gangnam-tennis-alert"
python -c "from src.daechi import fetch_daechi_slots; \
s=fetch_daechi_slots({'대치유수지':{'받기':True,'매일':[7,9,11,13,15,17,19]}}); \
print('빈자리', len(s), '건'); \
[print(x.place, x.date, x.time) for x in s[:10]]"
```
Expected: 오류 없이 `빈자리 N 건` 출력(미래 날짜의 A/B/C코트·시각). 0건이어도 **오류 없이** 끝나면 정상(그 시점 빈자리가 없을 뿐). `data-time=6`(19시)이 실제로 잡히는지 출력에서 확인.

> 만약 예외/0건이 의심되면: `python C:/Users/user/AppData/Local/Temp/analyze_daechi.py`로 저장본 구조와 대조하고, `data-time`/`<dt>` 순서 가정이 실제 응답과 맞는지 점검한다.

- [ ] **Step 2: 설정대로 동작 확인 (평일 19 / 토 7·9·19)**

Run:
```bash
cd "C:/Users/user/Desktop/gangnam-tennis-alert"
python -c "from src.daechi import fetch_daechi_slots; from src.settings_loader import load_settings; \
st,_=load_settings(); s=fetch_daechi_slots(st); \
print('설정대로 빈자리', len(s), '건'); \
[print(x.place, x.date, x.time) for x in s[:10]]"
```
Expected: 오류 없이 출력. 나오는 시각이 모두 19시(평일) 또는 7·9·19시(토)인지, 일요일은 없는지 눈으로 확인.

- [ ] **Step 3: `README.md` 감시 대상에 추가**

`- 감시 대상: 포이 테니스장, 강남세곡체육공원 테니스장` 줄을 아래로 교체:
```markdown
- 감시 대상: 포이·강남세곡 테니스장, 송파·잠실(유수지) 테니스장, 대치유수지 테니스장
```

- [ ] **Step 4: 전체 테스트 최종 확인**

Run: `python -m pytest -q`
Expected: 전부 PASS(실패 0)

- [ ] **Step 5: Commit**

```bash
REPO="C:/Users/user/Desktop/gangnam-tennis-alert"
git -C "$REPO" add README.md
git -C "$REPO" commit -m "docs(daechi): README 감시 대상에 대치유수지 추가" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 완료 기준(Definition of Done)

- [ ] `python -m pytest -q` 전부 통과(신규 7건 포함)
- [ ] 실제 사이트 조회가 오류 없이 동작(Task 4 Step 1·2)
- [ ] `data-time=6`(19시) 매핑이 실데이터에서 확인됨
- [ ] 기존 부품(`fetcher.py`·`esongpa.py`·`filters.py`·`notifier.py`) 무수정
- [ ] (배포는 별도) GitHub로 push 전 사용자 승인 — push해야 실제 가동

## 후속(이번 범위 밖)
- 알림 끝 예약 링크는 강남 1개 공용 유지(여러 시설 섞일 때 시설별 링크는 추후).
- 실측 HTML을 fixture 파일로 박제하는 통합 테스트는 선택(현재 인라인 축약본으로 충분).
