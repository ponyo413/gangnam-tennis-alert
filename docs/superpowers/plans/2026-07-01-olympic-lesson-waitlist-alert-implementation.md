# 올림픽공원 레슨 대기 알림 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 국민체육진흥공단 올림픽공원 테니스 레슨 대기 현황표에서 주중 19시 실외·실내 칸을 5분마다 읽어, 칸 값이 바뀌면(마감→숫자 열림 / 숫자→숫자 변동 / 숫자→마감 닫힘) 텔레그램으로 각각 1통 보낸다.

**Architecture:** 기존 봇의 "시설군마다 전용 부품" 구조를 따라 `src/olympic.py`를 신설한다. 로그인 없는 서버렌더 HTML을 정규식으로 파싱해 감시 칸의 **실제 값 dict**(`{"주중 실외 19시": "마감"}`)를 만들고, 직전 값 dict(`olympic_state.json`)와 비교해 전이를 감지한다. 강남·송파·잠실·대치유수지 부품은 손대지 않고, `main.py`에 `run_olympic_alert()` 호출 한 줄만 더한다. 읽기 전용.

**Tech Stack:** Python 3.13, requests(+urllib3 Retry 세션 재사용), 정규식 파싱(BeautifulSoup 미사용 — 기존 daechi.py와 동일), pytest, PyYAML 설정표.

---

## 파일 구조 (무엇을 만들고 고치나)

**신규**
- `src/olympic.py` — 표 파싱·상태판정·조회·알림문구 조립(전용 부품)
- `tests/test_olympic.py` — 위 부품 테스트

**수정(함수/블록 추가만, 기존 로직 변경 없음)**
- `src/config.py` — `OLYMPIC_URL` 상수 추가
- `src/notifier.py` — `format_olympic_alert()` 추가
- `src/state.py` — `save_olympic_state()`/`load_olympic_state()` 추가
- `src/settings_loader.py` — `올림픽공원레슨` 검증 특례 + `DEFAULT_SETTINGS` 블록 추가
- `src/main.py` — `run_olympic_alert()` + `main()` 배선
- `tests/test_notifier.py` · `tests/test_state.py` · `tests/test_settings_loader.py` · `tests/test_main.py` — 테스트 추가/수정
- `settings.yaml` · `settings.last_good.yaml` — `올림픽공원레슨` 블록 추가
- `.github/workflows/check.yml` · `.github/workflows/daily-summary.yml` — 캐시 목록에 `olympic_state.json` 추가
- `.gitignore` — `olympic_state.json` 추가(런타임 상태파일)

> 배포(git push)는 이 계획 밖 — 완료 후 사용자 승인받고 push한다.

---

### Task 1: 알림 문구 + URL 상수 (`config.py`, `notifier.py`)

**Files:**
- Modify: `src/config.py` (상수 1개 추가)
- Modify: `src/notifier.py` (함수 1개 + import 1개 추가)
- Test: `tests/test_notifier.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_notifier.py` 맨 아래에 추가

```python
# ── 올림픽공원 레슨 대기 알림 문구(3종: 열림/변동/닫힘) ──────────────
from src.notifier import format_olympic_alert


def test_olympic_alert_열림():
    """마감→숫자: '대기 열림' + 칸 이름 + 현재 숫자 + 신청 링크."""
    msg = format_olympic_alert("주중 실외 19시", "열림", cur="3")
    assert "대기 열림" in msg
    assert "주중 실외 19시" in msg
    assert "3" in msg
    assert "ksponco" in msg          # 대기 신청 링크(OLYMPIC_URL)


def test_olympic_alert_변동():
    """숫자→숫자: '변동' + 직전값 → 현재값 화살표."""
    msg = format_olympic_alert("주중 실내 19시", "변동", cur="15", prev="19")
    assert "변동" in msg
    assert "주중 실내 19시" in msg
    assert "19" in msg and "15" in msg


def test_olympic_alert_닫힘():
    """숫자→마감: '마감' + 칸 이름 + 직전 숫자."""
    msg = format_olympic_alert("주중 실외 19시", "닫힘", prev="3")
    assert "마감" in msg
    assert "주중 실외 19시" in msg
    assert "3" in msg
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_notifier.py -k olympic -v`
Expected: FAIL — `ImportError: cannot import name 'format_olympic_alert'`

- [ ] **Step 3: 최소 구현** — `src/config.py`의 `RESERVE_URL` 정의 바로 아래에 추가

```python
# 국민체육진흥공단 올림픽공원 테니스 레슨 '대기 현황'(조회 주소 겸 알림 링크)
OLYMPIC_URL = "https://www.ksponco.or.kr/spm/reservationStatus/tennis/waitList.do?textSize=normal"
```

- [ ] **Step 4: 최소 구현** — `src/notifier.py` 상단 import에 `OLYMPIC_URL` 추가하고, 파일 맨 아래에 함수 추가

`src/notifier.py:6`의 import 줄을 이렇게 바꾼다(끝에 `OLYMPIC_URL` 추가):
```python
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, RESERVE_URL, OLYMPIC_URL
```

파일 맨 아래에 추가:
```python
def format_olympic_alert(label: str, kind: str, cur: str = "", prev: str = "") -> str:
    """올림픽공원 레슨 대기 알림 문구를 만든다.

    label 예: '주중 실외 19시'. kind = '열림'/'변동'/'닫힘'.
    cur/prev = 그 칸의 현재/직전 표시값(숫자 문자열 등).
    """
    if kind == "열림":   # 마감/X → 숫자: 이제 대기 신청 가능
        return (
            f"🎾 올림픽공원 테니스 레슨 대기 열림!\n"
            f"📋 {label} — 지금 {cur}\n"
            f"👉 지금 대기 신청: {OLYMPIC_URL}"
        )
    if kind == "변동":   # 숫자 → 숫자: 대기 인원/자리 수가 바뀜
        return (
            f"🔔 올림픽공원 레슨 대기 변동\n"
            f"📋 {label} — {prev} → {cur}\n"
            f"👉 {OLYMPIC_URL}"
        )
    # 닫힘: 숫자 → 마감/X (대기 줄이 다시 닫힘)
    return (
        f"🔒 올림픽공원 레슨 대기 마감\n"
        f"📋 {label} (직전 {prev})"
    )
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_notifier.py -k olympic -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/config.py src/notifier.py tests/test_notifier.py
git commit -m "feat(olympic): 대기 알림 문구(열림/변동/닫힘) + OLYMPIC_URL 상수"
```

---

### Task 2: 직전 상태 저장/불러오기 (`state.py`)

**Files:**
- Modify: `src/state.py` (함수 2개 추가)
- Test: `tests/test_state.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_state.py` 맨 아래에 추가

```python
def test_올림픽_상태_저장_불러오기(tmp_path):
    """감시 칸의 현재 값 dict를 저장하고 그대로 다시 읽어야 함."""
    from src.state import save_olympic_state, load_olympic_state
    path = tmp_path / "olympic_state.json"
    state = {"주중 실외 19시": "마감", "주중 실내 19시": "3"}
    save_olympic_state(path, state)
    assert load_olympic_state(path) == state


def test_없는_올림픽상태파일은_빈_dict(tmp_path):
    """파일이 없으면(첫 실행) 빈 dict — 첫 실행 취급."""
    from src.state import load_olympic_state
    assert load_olympic_state(tmp_path / "none.json") == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_state.py -k 올림픽 -v`
Expected: FAIL — `ImportError: cannot import name 'save_olympic_state'`

- [ ] **Step 3: 최소 구현** — `src/state.py` 맨 아래에 추가

```python
def save_olympic_state(path, state: dict) -> None:
    """올림픽 감시 칸의 현재 값 dict를 JSON으로 저장."""
    Path(path).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def load_olympic_state(path) -> dict:
    """올림픽 감시 칸 상태 dict를 불러옴. 파일이 없거나 깨졌으면 빈 dict."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_state.py -k 올림픽 -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/state.py tests/test_state.py
git commit -m "feat(olympic): 직전 상태 dict 저장/불러오기(olympic_state.json)"
```

---

### Task 3: 값 비교 판정 `classify_change` (`olympic.py` 신설)

**Files:**
- Create: `src/olympic.py`
- Create: `tests/test_olympic.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_olympic.py` 새 파일

```python
"""올림픽공원 레슨 대기 감시 부품 테스트 — 순수 로직 + 고정 HTML + 네트워크 monkeypatch."""
from src.olympic import classify_change


def test_마감에서_숫자면_열림():
    assert classify_change("마감", "19") == "열림"


def test_숫자에서_다른숫자면_변동():
    assert classify_change("19", "17") == "변동"


def test_숫자에서_마감이면_닫힘():
    assert classify_change("17", "마감") == "닫힘"


def test_숫자에서_X면_닫힘():
    assert classify_change("19", "X") == "닫힘"


def test_같은_값이면_None():
    assert classify_change("19", "19") is None
    assert classify_change("마감", "마감") is None


def test_마감과_X_사이는_조용():
    """둘 다 대기 불가·숫자 없음 → 알림 없음."""
    assert classify_change("마감", "X") is None
    assert classify_change("X", "마감") is None


def test_처음_등장한_숫자는_열림():
    """직전 기록이 없던 칸(None)에 숫자가 뜨면 '열림'(첫 실행은 main이 별도 차단)."""
    assert classify_change(None, "19") == "열림"


def test_처음_등장한_마감은_조용():
    assert classify_change(None, "마감") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_olympic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.olympic'`

- [ ] **Step 3: 최소 구현** — `src/olympic.py` 새 파일

```python
# src/olympic.py
"""올림픽공원 테니스 레슨 '대기 현황표' 감시 — 로그인 없는 HTML 파싱(전용 부품).

강남·esongpa·대치유수지가 '코트 빈자리(취소표)'를 다루는 것과 달리, 여기서는
'레슨 대기 칸의 값 변화'를 본다. 칸 값 3종: 숫자(대기 가능·그 수)·'마감'(대기 마감)·'X'(레슨 없음).
값이 바뀌면(마감→숫자·숫자→숫자·숫자→마감) 알림, 마감↔X만 조용.
날짜 축이 없는 고정 주간표(주중/주말)라 '칸별 현재값 dict'만 다룬다.
"""


def _is_number(value):
    """값이 숫자(대기 가능)인지. None·'마감'·'X'는 False (None-안전)."""
    return str(value).strip().isdigit()


def classify_change(prev, cur):
    """칸 하나의 직전값(prev)→현재값(cur)으로 알림 종류를 정한다(순수함수).

    반환: '열림' / '변동' / '닫힘' / None(조용).
    - 값이 같으면 None.
    - 현재가 숫자면: 직전이 숫자 아님(마감/X/None) → '열림', 직전도 숫자(값 다름) → '변동'.
    - 현재가 숫자 아니면(마감/X): 직전이 숫자 → '닫힘', 아니면 None(마감↔X는 조용).
    """
    if prev == cur:
        return None
    if _is_number(cur):
        return "변동" if _is_number(prev) else "열림"
    return "닫힘" if _is_number(prev) else None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_olympic.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/olympic.py tests/test_olympic.py
git commit -m "feat(olympic): 값 비교 판정 classify_change(열림/변동/닫힘/조용)"
```

---

### Task 4: 표 파싱 `parse_olympic` + 대상 만들기 `build_targets` (`olympic.py`)

**Files:**
- Modify: `src/olympic.py` (import·상수·함수 추가)
- Test: `tests/test_olympic.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_olympic.py` 맨 아래에 추가

```python
from src.olympic import build_targets, parse_olympic

# 실측 구조 축약: 첫 칸=요일, 둘째 칸=코트, 셋째 칸부터 시간칸. 값=마감/숫자/X.
_SAMPLE = (
    "<table>"
    "<tr><th>요일</th><th>시간/코트</th><th>18시</th><th>19시</th><th>20시</th></tr>"
    "<tr><th>주중</th><th>실외</th><td>마감</td><td>마감</td><td>마감</td></tr>"
    "<tr><th>주중</th><th>실내</th><td>마감</td><td>3</td><td>X</td></tr>"
    "</table>"
)


def test_build_targets_받기off거나_없으면_빈목록():
    assert build_targets({"받기": False, "코트": ["실외"], "주중": [19]}) == []
    assert build_targets(None) == []


def test_build_targets_주중_두_코트():
    got = build_targets({"받기": True, "코트": ["실외", "실내"], "주중": [19]})
    assert set(got) == {("주중", "실외", 19), ("주중", "실내", 19)}


def test_build_targets_잘못된_코트는_무시():
    got = build_targets({"받기": True, "코트": ["실외", "옥상"], "주중": [19]})
    assert got == [("주중", "실외", 19)]


def test_parse_reads_target_cells():
    targets = [("주중", "실외", 19), ("주중", "실내", 19)]
    got = parse_olympic(_SAMPLE, targets)
    assert got == {"주중 실외 19시": "마감", "주중 실내 19시": "3"}


def test_parse_handles_X_and_column_shift():
    """19시 열 위치가 달라져도(헤더 지도로 찾음) 값을 정확히 읽는다."""
    html = (
        "<table>"
        "<tr><th>요일</th><th>시간/코트</th><th>20시</th><th>19시</th></tr>"
        "<tr><th>주중</th><th>실내</th><td>마감</td><td>X</td></tr>"
        "</table>"
    )
    assert parse_olympic(html, [("주중", "실내", 19)]) == {"주중 실내 19시": "X"}


def test_parse_skips_targets_not_in_table():
    """표에 없는 대상(주말)은 결과에 없다(예외 없이 건너뜀)."""
    assert parse_olympic(_SAMPLE, [("주말", "실외", 19)]) == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_olympic.py -k "targets or parse" -v`
Expected: FAIL — `ImportError: cannot import name 'build_targets'`

- [ ] **Step 3: 최소 구현** — `src/olympic.py`의 모듈 docstring 바로 아래에 `import re`와 상수·헬퍼를 넣고, 파일 아래쪽(`classify_change` 다음)에 함수 2개를 추가

docstring 다음 줄(파일 최상단 코드부)에 추가:
```python
import re

DAY_KEYS = ("주중", "주말", "수요일")   # 표 첫 칸(요일)에 나올 수 있는 값
COURT_KEYS = ("실외", "실내")            # 표 둘째 칸(코트)

# 표 파싱용 정규식(스크립트 제거 → <tr> → <th|td> 순)
_SCRIPT_RE = re.compile(r"<script.*?</script>", re.DOTALL | re.IGNORECASE)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<(t[hd])[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_HOUR_RE = re.compile(r"(\d+)\s*시")     # "19시" → 19


def _clean(fragment):
    """HTML 조각에서 태그 제거 + 공백 정리 → 순수 텍스트."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()
```

`classify_change` 아래(파일 맨 끝)에 추가:
```python
def build_targets(cfg):
    """설정(cfg) → 감시할 (요일, 코트, 시) 튜플 목록(순수함수).

    cfg 예: {"받기": True, "코트": ["실외","실내"], "주중": [19]}.
    받기=False·설정 없음 → []. 요일키(주중/주말/수요일) × 코트 × 시각을 모두 편다.
    """
    if not cfg or not cfg.get("받기"):
        return []
    courts = [c for c in cfg.get("코트", []) if c in COURT_KEYS]
    targets = []
    for day in DAY_KEYS:
        for hour in cfg.get(day, []):
            for court in courts:
                targets.append((day, court, hour))
    return targets


def _rows(html):
    """HTML → 표의 각 줄을 '칸 텍스트 목록'으로. (스크립트 제거 후 <tr>·<th/td> 파싱)"""
    body = _SCRIPT_RE.sub("", html)
    rows = []
    for tr in _TR_RE.findall(body):
        cells = [_clean(m.group(2)) for m in _CELL_RE.finditer(tr)]
        if cells:
            rows.append(cells)
    return rows


def _hour_columns(rows):
    """머리줄('시간/코트'가 든 줄)에서 {시각(int): 열번호} 지도를 만든다."""
    for cells in rows:
        if any("시간/코트" in c for c in cells):
            cols = {}
            for idx, c in enumerate(cells):
                m = _HOUR_RE.fullmatch(c.replace(" ", ""))
                if m:
                    cols[int(m.group(1))] = idx
            return cols
    return {}


def parse_olympic(html, targets):
    """감시 대상 칸의 현재 값만 dict로 뽑는다(순수 파싱).

    targets: (요일, 코트, 시) 튜플 목록.
    반환: {"주중 실외 19시": "마감", "주중 실내 19시": "3", ...} — 칸 실제 텍스트 그대로.
    표에서 못 찾은 칸은 그냥 빠진다(예외 안 냄).
    """
    rows = _rows(html)
    hour_cols = _hour_columns(rows)
    result = {}
    for day, court, hour in targets:
        col = hour_cols.get(hour)
        if col is None:
            continue
        for cells in rows:
            if len(cells) > col and cells[0] == day and cells[1] == court:
                result[f"{day} {court} {hour}시"] = cells[col]
                break
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_olympic.py -v`
Expected: PASS (14 passed — Task 3의 8개 + 이번 6개)

- [ ] **Step 5: 커밋**

```bash
git add src/olympic.py tests/test_olympic.py
git commit -m "feat(olympic): 표 파싱 parse_olympic + 감시대상 build_targets"
```

---

### Task 5: 조회 `fetch_olympic_states` + 문구 조립 `build_olympic_messages` (`olympic.py`)

**Files:**
- Modify: `src/olympic.py` (import·상수·함수 추가)
- Test: `tests/test_olympic.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_olympic.py` 맨 아래에 추가

```python
from src.olympic import build_olympic_messages, fetch_olympic_states


def test_build_messages_바뀐_칸만_문구():
    """실외는 마감→3(열림), 실내는 그대로 → 문구 1개(실외 열림)."""
    prev = {"주중 실외 19시": "마감", "주중 실내 19시": "19"}
    cur = {"주중 실외 19시": "3", "주중 실내 19시": "19"}
    msgs = build_olympic_messages(cur, prev)
    assert len(msgs) == 1
    assert "주중 실외 19시" in msgs[0] and "대기 열림" in msgs[0]


def test_build_messages_변동은_화살표():
    prev = {"주중 실내 19시": "19"}
    cur = {"주중 실내 19시": "15"}
    msgs = build_olympic_messages(cur, prev)
    assert len(msgs) == 1
    assert "19" in msgs[0] and "15" in msgs[0]


def test_fetch_받기off는_빈dict():
    assert fetch_olympic_states({"올림픽공원레슨": {"받기": False}}) == {}
    assert fetch_olympic_states({}) == {}


def test_fetch_네트워크오류면_None(monkeypatch):
    """조회가 터지면 예외를 밖으로 던지지 않고 None(main이 직전 유지)."""
    def boom(self, *a, **k):
        raise RuntimeError("연결 실패")
    monkeypatch.setattr("requests.Session.get", boom)
    settings = {"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": [19]}}
    assert fetch_olympic_states(settings) is None


def test_fetch_정상파싱(monkeypatch):
    html = (
        "<table>"
        "<tr><th>요일</th><th>시간/코트</th><th>19시</th></tr>"
        "<tr><th>주중</th><th>실외</th><td>마감</td></tr>"
        "</table>"
    )

    class FakeResp:
        text = html
        encoding = "utf-8"

    monkeypatch.setattr("requests.Session.get", lambda self, *a, **k: FakeResp())
    settings = {"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": [19]}}
    assert fetch_olympic_states(settings) == {"주중 실외 19시": "마감"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_olympic.py -k "messages or fetch" -v`
Expected: FAIL — `ImportError: cannot import name 'build_olympic_messages'`

- [ ] **Step 3: 최소 구현** — `src/olympic.py` 상단 import부에 아래 3줄을 `import re` 다음에 추가

```python
from src.config import OLYMPIC_URL
from src.http_session import make_session
from src.notifier import format_olympic_alert
```

그리고 상수부(`COURT_KEYS` 아래)에 추가:
```python
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
REQUEST_TIMEOUT = 8   # 한 요청 최대 기다림(초)
```

파일 맨 아래에 함수 2개 추가:
```python
def build_olympic_messages(current, previous):
    """직전(previous)·현재(current) 값 dict를 비교해 보낼 알림 문구 목록을 만든다.

    current의 각 칸을 classify_change로 판정하고, 종류가 있으면 문구 1개씩.
    """
    messages = []
    for label, cur in current.items():
        prev = previous.get(label)
        kind = classify_change(prev, cur)
        if kind:
            messages.append(format_olympic_alert(label, kind, cur, prev or ""))
    return messages


def fetch_olympic_states(settings):
    """설정 기반으로 대기 현황표를 조회해 감시 칸의 현재 값 dict를 돌려준다.

    반환: dict(정상) / {}(받기 off·대상 0개) / None(조회·파싱 실패 → main이 직전 유지).
    조회 예외는 밖으로 던지지 않는다(다른 시설 알림 보호).
    """
    cfg = settings.get("올림픽공원레슨")
    targets = build_targets(cfg)
    if not targets:
        return {}                       # 감시 끔 → 조회 안 함
    try:
        session = make_session(HEADERS)
        r = session.get(OLYMPIC_URL, timeout=REQUEST_TIMEOUT)
        r.encoding = "utf-8"            # 표 한글 깨짐 방지
        return parse_olympic(r.text, targets)
    except Exception as e:
        print(f"[올림픽공원 조회 실패] {e}")
        return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_olympic.py -v`
Expected: PASS (19 passed — 누적)

- [ ] **Step 5: 커밋**

```bash
git add src/olympic.py tests/test_olympic.py
git commit -m "feat(olympic): 표 조회 fetch_olympic_states + 문구 조립 build_olympic_messages"
```

---

### Task 6: 설정표 검증 특례 + 기본값 (`settings_loader.py`)

**Files:**
- Modify: `src/settings_loader.py` (상수·함수·분기·기본값 추가)
- Test: `tests/test_settings_loader.py` (테스트 추가 + 기존 1개 수정)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_settings_loader.py` 맨 아래에 추가

```python
# ── 올림픽공원레슨 블록(빈자리 시설과 모양이 다름: 코트=글자목록, 요일=주중/주말/수요일) ──
def test_올림픽_블록_유효():
    data = {"올림픽공원레슨": {"받기": True, "코트": ["실외", "실내"], "주중": [19]}}
    assert validate_settings(data) == data


def test_올림픽_코트값_틀리면_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["옥상"], "주중": [19]}})


def test_올림픽_이상한_요일키_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["실외"], "월화": [19]}})


def test_올림픽_시간이_숫자목록_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": "저녁"}})


def test_기본값_올림픽공원레슨_시간대():
    assert DEFAULT_SETTINGS["올림픽공원레슨"] == {"받기": True, "코트": ["실외", "실내"], "주중": [19]}
```

또한 **기존 테스트 1개를 수정**한다 — `test_기본값에_운영_시설이_모두_있다`의 집합에 `올림픽공원레슨` 추가:
```python
def test_기본값에_운영_시설이_모두_있다():
    """비상 기본값에도 운영 중인 시설이 다 들어 있어야 한다(폴백 시 알림 끊김 방지)."""
    assert set(DEFAULT_SETTINGS) == {"강남", "송파", "잠실", "대치유수지", "올림픽공원레슨"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_settings_loader.py -v`
Expected: FAIL — `test_올림픽_블록_유효`가 ValueError(코트 키 거부) + `test_기본값에_운영_시설이_모두_있다` 불일치

- [ ] **Step 3: 최소 구현** — `src/settings_loader.py` 수정

(a) `DEFAULT_SETTINGS`의 `대치유수지` 줄 다음에 한 줄 추가:
```python
    "올림픽공원레슨": {"받기": True, "코트": ["실외", "실내"], "주중": [19]},
```

(b) `WEEKDAY_KEYS`/`TIME_KEYS` 근처(모듈 상단 상수부)에 추가:
```python
# 올림픽공원레슨 블록 전용 허용값(빈자리 시설과 형식이 달라 따로 검증)
_OLYMPIC_COURTS = {"실외", "실내"}
_OLYMPIC_DAY_KEYS = {"주중", "주말", "수요일"}
```

(c) `validate_settings`보다 위에 새 함수 추가:
```python
def _validate_olympic_block(cfg):
    """올림픽공원레슨 블록 검증 — 받기(bool) + 코트(실외/실내 목록) + 요일(주중/주말/수요일→시각목록)."""
    if not isinstance(cfg.get("받기"), bool):
        raise ValueError("'올림픽공원레슨'의 '받기'는 true 또는 false여야 합니다")
    courts = cfg.get("코트", [])
    if not (isinstance(courts, list) and all(c in _OLYMPIC_COURTS for c in courts)):
        raise ValueError("'올림픽공원레슨'의 '코트'는 실외/실내 목록이어야 합니다")
    for key, val in cfg.items():
        if key in ("받기", "코트"):
            continue
        if key not in _OLYMPIC_DAY_KEYS:
            raise ValueError(f"'올림픽공원레슨'의 '{key}'는 주중/주말/수요일이어야 합니다")
        if not (isinstance(val, list) and all(isinstance(h, int) for h in val)):
            raise ValueError(f"'올림픽공원레슨 {key}'의 시간은 숫자 목록이어야 합니다(예: [19])")
```

(d) `validate_settings` 안, `for fac, cfg in data.items():` 루프에서 `if not isinstance(cfg, dict):` 검사 **다음에** 특례 분기 추가:
```python
        if fac == "올림픽공원레슨":
            _validate_olympic_block(cfg)
            continue
```

> 참고: `validate_settings`는 시설명 화이트리스트가 없고 검사 후 `data`를 그대로 반환한다.
> 특례 분기가 먼저 `continue`하므로 올림픽 블록은 빈자리용 시간키 검사를 타지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_settings_loader.py -v`
Expected: PASS (기존 + 신규 모두 통과)

- [ ] **Step 5: 커밋**

```bash
git add src/settings_loader.py tests/test_settings_loader.py
git commit -m "feat(olympic): 설정표 올림픽 블록 검증 특례 + 기본값"
```

---

### Task 7: `main`에 감시 배선 (`main.py`)

**Files:**
- Modify: `src/main.py` (import·상수·함수·호출 추가)
- Test: `tests/test_main.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_main.py` 맨 아래에 추가

```python
# ─────────────────────────────────────────────────────────────
# 올림픽공원 레슨 대기 감시 — run_olympic_alert 3분기
# ─────────────────────────────────────────────────────────────
def test_run_olympic_첫실행은_저장만_알림없음(tmp_path, monkeypatch):
    import src.main as m
    from src.state import load_olympic_state
    sent = []
    path = str(tmp_path / "olympic_state.json")
    monkeypatch.setattr(m, "OLYMPIC_STATE_PATH", path)
    monkeypatch.setattr(m, "load_settings", lambda: ({}, None))
    monkeypatch.setattr(m, "fetch_olympic_states", lambda settings: {"주중 실외 19시": "마감"})
    monkeypatch.setattr(m, "send_telegram", lambda text: sent.append(text) or True)
    m.run_olympic_alert()
    assert sent == []                                   # 첫 실행 알림 없음
    assert load_olympic_state(path) == {"주중 실외 19시": "마감"}   # 기준 저장됨


def test_run_olympic_값바뀌면_알림(tmp_path, monkeypatch):
    import src.main as m
    from src.state import save_olympic_state
    path = str(tmp_path / "olympic_state.json")
    save_olympic_state(path, {"주중 실외 19시": "마감"})   # 직전=마감
    sent = []
    monkeypatch.setattr(m, "OLYMPIC_STATE_PATH", path)
    monkeypatch.setattr(m, "load_settings", lambda: ({}, None))
    monkeypatch.setattr(m, "fetch_olympic_states", lambda settings: {"주중 실외 19시": "3"})  # 지금=3
    monkeypatch.setattr(m, "send_telegram", lambda text: sent.append(text) or True)
    m.run_olympic_alert()
    assert len(sent) == 1 and "대기 열림" in sent[0]


def test_run_olympic_조회실패는_실패누적(tmp_path, monkeypatch):
    import src.main as m
    saved = {}
    monkeypatch.setattr(m, "OLYMPIC_STATE_PATH", str(tmp_path / "olympic_state.json"))
    monkeypatch.setattr(m, "FAIL_PATH", str(tmp_path / "failures.json"))
    monkeypatch.setattr(m, "load_settings", lambda: ({}, None))
    monkeypatch.setattr(m, "fetch_olympic_states", lambda settings: None)   # 조회 실패
    monkeypatch.setattr(m, "load_failures", lambda path: {})
    monkeypatch.setattr(m, "save_failures", lambda path, data: saved.update(data))
    m.run_olympic_alert()
    assert saved.get("올림픽공원레슨") == 1


def test_main_watch가_올림픽감시_호출(monkeypatch):
    """watch 모드가 run_olympic_alert를 호출한다(배선 확인)."""
    import sys
    import src.main as m
    called = []
    monkeypatch.setattr(sys, "argv", ["main"])
    monkeypatch.setattr(m, "run_vacancy_alert", lambda: None)
    monkeypatch.setattr(m, "run_application_alert", lambda: None)
    monkeypatch.setattr(m, "run_olympic_alert", lambda: called.append(1))
    monkeypatch.setattr(m, "maybe_send_daily_summary", lambda now: None)
    assert m.main() == 0
    assert called == [1]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_main.py -k olympic -v`
Expected: FAIL — `AttributeError: module 'src.main' has no attribute 'run_olympic_alert'`

- [ ] **Step 3: 최소 구현** — `src/main.py` 수정

(a) import부 수정 — 두 가지:

① `from src.daechi import ...` 아래에 올림픽 부품 import 한 줄 추가:
```python
from src.olympic import fetch_olympic_states, build_olympic_messages
```

② `src.state`는 이미 여러 이름을 묶어 import 중이므로, **그 기존 묶음 끝**에 두 이름을 더한다
(새 import 줄을 따로 만들지 말 것). 기존:
```python
from src.state import (load_slots, save_slots, load_status, save_status,
                       load_failures, save_failures, load_fail_count, save_fail_count,
                       load_daechi_fetch_time, save_daechi_fetch_time,
                       load_summary_date, save_summary_date)
```
→ 뒤에 `save_olympic_state, load_olympic_state`를 붙여서:
```python
from src.state import (load_slots, save_slots, load_status, save_status,
                       load_failures, save_failures, load_fail_count, save_fail_count,
                       load_daechi_fetch_time, save_daechi_fetch_time,
                       load_summary_date, save_summary_date,
                       save_olympic_state, load_olympic_state)
```

(b) 상수부(`SUMMARY_HOUR` 근처)에 추가:
```python
OLYMPIC_STATE_PATH = "olympic_state.json"   # 올림픽 감시 칸의 직전 값(캐시 보관)
```

(c) `run_application_alert` 함수 다음에 새 함수 추가:
```python
def run_olympic_alert():
    """③ 올림픽공원 레슨 대기 감시 — 칸 값이 바뀌면(열림/변동/닫힘) 각각 1통.

    첫 실행은 현재 상태만 저장(알림 없음). 조회 실패는 실패 누적 + 직전 상태 유지.
    받기 off/파싱 0건이면 조용히 넘어가고 직전 상태를 건드리지 않는다.
    """
    settings, _ = load_settings()
    current = fetch_olympic_states(settings)   # dict / {} / None(실패)
    if current is None:                        # 조회·파싱 실패 → 실패 누적, 직전 상태 유지
        failures = load_failures(FAIL_PATH)
        failures["올림픽공원레슨"] = failures.get("올림픽공원레슨", 0) + 1
        save_failures(FAIL_PATH, failures)
        return
    if not current:                            # 감시 끔/대상 0 → 조용히(직전 상태 보존)
        return
    is_first = not Path(OLYMPIC_STATE_PATH).exists()
    if is_first:
        print(f"[올림픽 첫 실행] {len(current)}칸 기준 저장(알림 생략)")
    else:
        previous = load_olympic_state(OLYMPIC_STATE_PATH)
        messages = build_olympic_messages(current, previous)
        for text in messages:
            send_telegram(text)
        print(f"[올림픽 점검] 알림 {len(messages)}건")
    save_olympic_state(OLYMPIC_STATE_PATH, current)
```

(d) `main()`의 watch 경로에 호출 한 줄 추가 — `run_application_alert()` 다음 줄:
```python
    run_vacancy_alert()
    run_application_alert()
    run_olympic_alert()   # ③ 올림픽공원 레슨 대기 감시
    maybe_send_daily_summary(datetime.now(KST))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (기존 + 올림픽 4개)

- [ ] **Step 5: 커밋**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat(olympic): main에 run_olympic_alert 배선(watch 모드)"
```

---

### Task 8: 설정표·워크플로·gitignore 배선 + 전체 검증

**Files:**
- Modify: `settings.yaml`, `settings.last_good.yaml` (블록 추가)
- Modify: `.github/workflows/check.yml`, `.github/workflows/daily-summary.yml` (캐시 목록)
- Modify: `.gitignore` (상태파일)

- [ ] **Step 1: `settings.yaml` 맨 아래에 블록 추가**

```yaml

올림픽공원레슨:            # 국민체육진흥공단 올림픽공원 테니스 레슨 대기(로그인 없음, 5분마다 조회)
  받기: true              # 끄려면 false 로만 바꾸면 끝
  코트: [실외, 실내]        # 감시할 코트(실외/실내). 둘 다면 둘 다 적기
  주중: [19]              # 평일 저녁 7시. 나중에 [18, 19, 20]처럼 늘리기 가능
  # 주말: [10]            # (선택) 주말도 보려면 주석(#) 지우고 시각 적기
```

> **`settings.last_good.yaml`은 손대지 않는다** — 이 파일은 `.gitignore` 대상(런타임 자동 생성)이고,
> 아래 Step 5 스모크가 `load_settings()`를 부르면서 방금 고친 `settings.yaml`을 검증·통과시켜
> **자동으로 새 내용(올림픽 블록 포함)으로 갱신**한다. 그래서 수동 편집·커밋 모두 불필요.

- [ ] **Step 2: `.github/workflows/check.yml` 캐시 목록에 한 줄 추가**

`path: |` 아래 `daechi_fetch.json` 다음 줄에 추가(들여쓰기 동일하게 12칸):
```yaml
            olympic_state.json
```

- [ ] **Step 3: `.github/workflows/daily-summary.yml` 캐시 목록에도 같은 한 줄 추가**

`daechi_fetch.json` 다음 줄에 `            olympic_state.json` 추가.
> 두 워크플로가 같은 캐시(tennis-state-v4)를 공유하므로 목록을 반드시 똑같이 맞춘다
> (한쪽에서 빠지면 그 워크플로가 캐시를 저장할 때 파일이 누락돼 다음 실행이 초기화된다).
> 캐시 key는 그대로 둔다 — 파일 추가는 하위호환. 배포 후 첫 실행은 기준값만 저장(알림 없음).

- [ ] **Step 4: `.gitignore`에 상태파일 추가**

`read_fail.json` 다음 줄에 추가:
```
olympic_state.json
```

- [ ] **Step 5: 실제 사이트 대상 읽기 전용 스모크(텔레그램 발송 없음, last_good도 자동 갱신)**

Run:
```bash
python -c "from src.settings_loader import load_settings; from src.olympic import fetch_olympic_states; print(fetch_olympic_states(load_settings()[0]))"
```
Expected: 실제 현재 값 출력 — 예 `{'주중 실외 19시': '마감', '주중 실내 19시': '마감'}`
(값이 dict로 나오면 조회·파싱·설정 배선이 실제 사이트에서 동작하는 것. `None`이면 사이트 접속 문제.)

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `python -m pytest -q`
Expected: PASS — 기존 + 신규 전부 통과, 실패 0

- [ ] **Step 7: 커밋** (`settings.last_good.yaml`은 gitignore라 넣지 않는다)

```bash
git add settings.yaml .github/workflows/check.yml .github/workflows/daily-summary.yml .gitignore
git commit -m "feat(olympic): 설정표·워크플로 캐시·gitignore 배선(주중 19시 실내외)"
```

---

## 자체 검토 결과(계획↔설계 대조)

- **설계 §2 요구(칸 값 변화마다 1통·마감↔X 조용)** → Task 3 `classify_change` + Task 5 `build_olympic_messages` (열림/변동/닫힘/None) ✅
- **§3 사이트 구조(17칸·rowspan 없음·시간→열 지도)** → Task 4 `parse_olympic`·`_hour_columns`(열 위치 견딤 테스트 포함) ✅
- **§5.1 fetch(dict/{}/None)** → Task 5 `fetch_olympic_states` 3분기 + 예외 안 던짐 테스트 ✅
- **§5.2·5.3 설정표+검증 특례** → Task 6(`_validate_olympic_block`·기본값·기존 테스트 수정) ✅
- **§5.4 상태 저장** → Task 2 `save/load_olympic_state` ✅
- **§5.5 문구 3종** → Task 1 `format_olympic_alert` ✅
- **§5.6 main 배선(첫 실행 저장만·실패 누적)** → Task 7 `run_olympic_alert` + main 호출 ✅
- **§5.7 URL 상수** → Task 1 `OLYMPIC_URL` ✅
- **§5.8 캐시 목록(2개 워크플로)** → Task 8 Step 3·4 ✅
- **§8 실패는 아침 요약에 합류** → Task 7이 `failures["올림픽공원레슨"]` 누적(기존 `format_summary(failures=…)`가 자동 표기) ✅
- **§10 읽기 전용·기존 부품 무수정** → 모든 Task가 추가만, 강남/esongpa/daechi/differ/filters 불변 ✅

## 배포(이 계획 밖 — 완료 후 사용자 승인)

- 이 저장소의 "가동"은 **git push**다(GitHub Actions가 5분마다 실행). push 전 사용자 승인 필요.
- DB·마이그레이션 없음. push 후 **첫 5분 실행은 기준값만 저장(알림 없음)**, 그 다음 실행부터 변화 감지.
- 배포 후 확인: Actions 로그에 `[올림픽 첫 실행]` → 이후 `[올림픽 점검] 알림 N건`. 실제 마감→숫자 순간에 텔레그램 도착.
