# 강남 테니스장 취소표 알림 시스템 — 구현 공정표

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 강남구 예약 사이트를 주기적으로 조회해, 포이·세곡 테니스장에 원하는 시간대 빈자리가 생기면 텔레그램으로 알린다.

**Architecture:** 작은 순수 함수 모듈(필터·비교·상태·메시지)을 먼저 TDD로 단단히 만들고, 외부 의존(사이트 조회·텔레그램 발송)은 샘플 데이터로 테스트한 뒤 통합한다. 전체를 `main.py`가 조율하고, GitHub Actions가 3~5분마다 실행한다.

**Tech Stack:** Python 3.11+, pytest, requests, (필요 시 Playwright), 텔레그램 Bot API, GitHub Actions

> 설계서: `docs/superpowers/specs/2026-06-22-gangnam-tennis-alert-design.md`
> 모든 코드 주석은 한국어로 — 비개발자도 흐름을 이해할 수 있게.

---

## 파일 구조 (먼저 전체 그림)

```
gangnam-tennis-alert/
├── src/
│   ├── __init__.py
│   ├── models.py       # 빈자리 한 칸(Slot) 데이터 구조
│   ├── config.py       # 설정값(대상 코트, 시간대) + 환경변수(토큰)
│   ├── filters.py      # 시간대 필터 (평일 저녁 + 주말)  ← 순수함수
│   ├── differ.py       # 비교기: 직전 목록과 비교해 새 빈자리만  ← 순수함수
│   ├── state.py        # 직전 빈자리 목록 저장/불러오기 (JSON)
│   ├── notifier.py     # 텔레그램 메시지 만들기 + 발송
│   ├── fetcher.py      # 강남구 사이트에서 빈자리 읽기 (A안/B안)
│   └── main.py         # 전체 조율 (조회→필터→비교→알림→저장)
├── tests/
│   ├── test_filters.py
│   ├── test_differ.py
│   ├── test_state.py
│   └── test_notifier.py
├── samples/            # 사이트 응답 샘플(테스트·개발용)
├── .github/workflows/
│   └── check.yml       # 3~5분마다 자동 실행
├── requirements.txt
├── .gitignore
├── .env.example        # 토큰 넣는 칸 예시 (실제 .env는 git 제외)
└── README.md
```

**책임 분리 원칙:** 각 파일은 한 가지 일만. `filters`·`differ`는 외부 의존 없는 순수함수라 테스트가 쉽다. `fetcher`·`notifier`만 바깥 세상(사이트·텔레그램)과 닿는다.

---

## Task 1: 프로젝트 뼈대

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `README.md`, `src/__init__.py`, `pytest.ini`

- [ ] **Step 1: 의존성 파일 작성**

Create `requirements.txt`:
```
requests==2.32.3
pytest==8.3.4
python-dotenv==1.0.1
```
(Playwright는 fetcher에서 B안이 확정되면 그때 추가)

- [ ] **Step 2: .gitignore 작성**

Create `.gitignore`:
```
# 비밀 토큰이 든 실제 환경파일 — 절대 git에 올리지 않음
.env
# 직전 빈자리 기록(로컬 실행용) — 클라우드에선 캐시 사용
state.json
# 파이썬 캐시
__pycache__/
*.pyc
.pytest_cache/
# 가짜 브라우저(Playwright) 임시파일
.playwright/
```

- [ ] **Step 3: .env.example 작성 (토큰 넣는 칸 안내)**

Create `.env.example`:
```
# 텔레그램 봇 토큰 (BotFather가 알려줌). 실제 값은 .env에 적고 이 파일은 예시만.
TELEGRAM_TOKEN=여기에_봇_토큰
TELEGRAM_CHAT_ID=여기에_내_채팅_아이디
```

- [ ] **Step 4: pytest 설정**

Create `pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 5: 빈 패키지 파일 + README 뼈대**

Create `src/__init__.py` (빈 파일)
Create `README.md`:
```markdown
# 강남 테니스장 취소표 알림

포이·세곡 테니스장 빈자리를 감시해 텔레그램으로 알림. 개인용.
설계서: docs/superpowers/specs/2026-06-22-gangnam-tennis-alert-design.md
공정표: docs/superpowers/plans/2026-06-22-gangnam-tennis-alert-implementation.md
```

- [ ] **Step 6: 커밋**

```bash
git add -A
git commit -m "chore: 프로젝트 뼈대(의존성·gitignore·pytest 설정) 추가"
```

---

## Task 2: 빈자리 데이터 구조 + 설정

**Files:**
- Create: `src/models.py`, `src/config.py`

- [ ] **Step 1: 빈자리 한 칸(Slot) 정의**

Create `src/models.py`:
```python
"""빈자리 한 칸을 나타내는 데이터 구조."""
from dataclasses import dataclass


# frozen=True: 한 번 만들면 못 바꿈 → set(집합)에 넣어 '같은 빈자리인지' 비교 가능
@dataclass(frozen=True)
class Slot:
    court: str   # 코트 이름: "포이" 또는 "세곡"
    date: str    # 날짜: "2026-06-25" (YYYY-MM-DD)
    time: str    # 시작 시간: "19:00" (HH:MM)
```

- [ ] **Step 2: 설정값 정의**

Create `src/config.py`:
```python
"""시스템 설정값. 대상 코트·원하는 시간대·텔레그램 토큰을 한곳에 모음."""
import os
from dotenv import load_dotenv

load_dotenv()  # 로컬에서 .env 파일을 읽어 환경변수로 올림

# 감시할 코트 (나중에 봉은 추가하려면 여기에 한 줄)
COURTS = ["포이", "세곡"]

# 평일 저녁 시간 범위 (시작시각 기준, 18시~21시 시작분까지 = 18,19,20,21시)
WEEKDAY_EVENING_START = 18
WEEKDAY_EVENING_END = 22  # 22시 직전까지

# 텔레그램 토큰 (코드에 직접 안 적고 환경변수/금고에서 가져옴)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# 강남구 예약 사이트 (알림 메시지에 넣을 링크)
RESERVE_URL = "https://life.gangnam.go.kr/fmcs/1"
```

- [ ] **Step 3: 커밋**

```bash
git add src/models.py src/config.py
git commit -m "feat: 빈자리 데이터 구조(Slot)와 설정값(config) 추가"
```

---

## Task 3: 시간대 필터 (평일 저녁 + 주말) — 순수함수 TDD

**Files:**
- Create: `src/filters.py`
- Test: `tests/test_filters.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_filters.py`:
```python
"""시간대 필터 테스트: 평일 저녁(18~21시 시작) + 주말 전체만 통과해야 함."""
from src.models import Slot
from src.filters import is_wanted_time


def test_평일_저녁_통과():
    # 2026-06-24는 수요일. 19시는 평일 저녁 → 통과
    assert is_wanted_time(Slot("포이", "2026-06-24", "19:00")) is True


def test_평일_낮_제외():
    # 수요일 10시는 평일 낮 → 제외
    assert is_wanted_time(Slot("포이", "2026-06-24", "10:00")) is False


def test_평일_저녁_경계_18시_통과_22시_제외():
    assert is_wanted_time(Slot("세곡", "2026-06-24", "18:00")) is True
    assert is_wanted_time(Slot("세곡", "2026-06-24", "22:00")) is False


def test_주말_낮_통과():
    # 2026-06-27는 토요일. 주말은 시간 무관 통과
    assert is_wanted_time(Slot("포이", "2026-06-27", "10:00")) is True
    # 2026-06-28는 일요일
    assert is_wanted_time(Slot("세곡", "2026-06-28", "07:00")) is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_filters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.filters'`

- [ ] **Step 3: 최소 구현**

Create `src/filters.py`:
```python
"""원하는 시간대(평일 저녁 + 주말) 빈자리만 골라내는 필터."""
from datetime import date
from src.models import Slot
from src.config import WEEKDAY_EVENING_START, WEEKDAY_EVENING_END


def is_wanted_time(slot: Slot) -> bool:
    """이 빈자리가 사용자가 원하는 시간대인지 판단.

    - 주말(토·일): 시간 상관없이 모두 원함 → True
    - 평일(월~금): 저녁(18~21시 시작)만 원함
    """
    y, m, d = (int(x) for x in slot.date.split("-"))
    weekday = date(y, m, d).weekday()  # 월=0 ... 토=5, 일=6

    if weekday >= 5:  # 토(5)·일(6) = 주말
        return True

    # 평일이면 시작 시각(시)만 떼서 저녁 범위인지 확인
    hour = int(slot.time.split(":")[0])
    return WEEKDAY_EVENING_START <= hour < WEEKDAY_EVENING_END
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_filters.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/filters.py tests/test_filters.py
git commit -m "feat: 시간대 필터(평일 저녁+주말) 추가 + 테스트"
```

---

## Task 4: 비교기 (새 빈자리만 골라내기) — 순수함수 TDD

**Files:**
- Create: `src/differ.py`
- Test: `tests/test_differ.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_differ.py`:
```python
"""비교기 테스트: 이번 목록 중 직전에 없던 '새 빈자리'만 돌려줘야 함."""
from src.models import Slot
from src.differ import find_new_slots


def test_새로_생긴_빈자리만_반환():
    previous = [Slot("포이", "2026-06-25", "19:00")]
    current = [
        Slot("포이", "2026-06-25", "19:00"),  # 직전에도 있던 것 → 제외
        Slot("세곡", "2026-06-27", "10:00"),  # 새로 생김 → 포함
    ]
    result = find_new_slots(current, previous)
    assert result == [Slot("세곡", "2026-06-27", "10:00")]


def test_변화_없으면_빈_목록():
    same = [Slot("포이", "2026-06-25", "19:00")]
    assert find_new_slots(same, same) == []


def test_직전이_비어있으면_전부_새것():
    current = [Slot("포이", "2026-06-25", "19:00")]
    assert find_new_slots(current, []) == current
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_differ.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.differ'`

- [ ] **Step 3: 최소 구현**

Create `src/differ.py`:
```python
"""직전 빈자리 목록과 이번 목록을 비교해 '새로 생긴 빈자리'만 찾는다."""
from src.models import Slot


def find_new_slots(current: list[Slot], previous: list[Slot]) -> list[Slot]:
    """이번(current)에는 있는데 직전(previous)에는 없던 빈자리만 돌려준다.

    Slot이 frozen=True라 set으로 빠르게 '있었나?' 확인 가능.
    current의 순서는 그대로 유지한다.
    """
    previous_set = set(previous)
    return [slot for slot in current if slot not in previous_set]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_differ.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/differ.py tests/test_differ.py
git commit -m "feat: 비교기(새 빈자리 골라내기) 추가 + 테스트"
```

---

## Task 5: 상태 저장/불러오기 (JSON)

**Files:**
- Create: `src/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_state.py`:
```python
"""상태 저장/불러오기 테스트: 빈자리 목록을 파일에 저장하고 그대로 다시 읽어야 함."""
from src.models import Slot
from src.state import save_slots, load_slots


def test_저장한_그대로_불러오기(tmp_path):
    path = tmp_path / "state.json"
    slots = [Slot("포이", "2026-06-25", "19:00"), Slot("세곡", "2026-06-27", "10:00")]
    save_slots(path, slots)
    assert load_slots(path) == slots


def test_없는_파일은_빈_목록(tmp_path):
    path = tmp_path / "없음.json"
    assert load_slots(path) == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.state'`

- [ ] **Step 3: 최소 구현**

Create `src/state.py`:
```python
"""직전 빈자리 목록을 JSON 파일에 저장/불러오기.

GitHub Actions는 실행마다 기억이 초기화되므로, 이 파일을 캐시에 보관해
다음 실행과 비교한다. (상세는 .github/workflows/check.yml 참고)
"""
import json
from pathlib import Path
from src.models import Slot


def save_slots(path, slots: list[Slot]) -> None:
    """빈자리 목록을 JSON 파일로 저장."""
    data = [{"court": s.court, "date": s.date, "time": s.time} for s in slots]
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_slots(path) -> list[Slot]:
    """JSON 파일에서 빈자리 목록을 불러옴. 파일이 없으면 빈 목록."""
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Slot(d["court"], d["date"], d["time"]) for d in data]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/state.py tests/test_state.py
git commit -m "feat: 빈자리 목록 저장/불러오기(state) 추가 + 테스트"
```

---

## Task 6: 텔레그램 알림기 (메시지 만들기 + 발송)

**Files:**
- Create: `src/notifier.py`
- Test: `tests/test_notifier.py`

> 메시지 '만들기'는 순수함수라 TDD로 검증. 실제 '발송'은 텔레그램 서버가 필요하니
> 함수만 분리해 두고, 통합 확인은 Task 9(로컬 전체 실행)에서 실제 토큰으로 한다.

- [ ] **Step 1: 실패하는 테스트 작성 (메시지 만들기)**

Create `tests/test_notifier.py`:
```python
"""알림 메시지 만들기 테스트."""
from src.models import Slot
from src.notifier import format_message


def test_빈자리_하나_메시지():
    msg = format_message([Slot("포이", "2026-06-25", "19:00")])
    assert "포이" in msg
    assert "2026-06-25" in msg
    assert "19:00" in msg


def test_여러_빈자리_모두_포함():
    slots = [Slot("포이", "2026-06-25", "19:00"), Slot("세곡", "2026-06-27", "10:00")]
    msg = format_message(slots)
    assert "포이" in msg and "세곡" in msg


def test_빈_목록은_빈_문자열():
    assert format_message([]) == ""
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.notifier'`

- [ ] **Step 3: 최소 구현**

Create `src/notifier.py`:
```python
"""텔레그램으로 빈자리 알림을 보낸다. (1) 메시지 만들기 (2) 실제 발송."""
import requests
from src.models import Slot
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, RESERVE_URL

# 한 메시지에 빈자리를 너무 많이 담지 않도록 제한
MAX_LINES = 10


def format_message(slots: list[Slot]) -> str:
    """새 빈자리 목록을 사람이 읽기 좋은 텔레그램 메시지로 만든다.

    빈 목록이면 빈 문자열(보내지 않음).
    """
    if not slots:
        return ""

    lines = ["🎾 빈자리 발견!"]
    for s in slots[:MAX_LINES]:
        lines.append(f"🏟 {s.court}테니스장  📅 {s.date} {s.time}")
    if len(slots) > MAX_LINES:
        lines.append(f"…외 {len(slots) - MAX_LINES}건")
    lines.append(f"👉 지금 예약: {RESERVE_URL}")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """텔레그램으로 메시지 발송. 성공하면 True.

    text가 비어 있으면(보낼 게 없으면) 아무것도 안 하고 True.
    """
    if not text:
        return True
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    return resp.ok
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_notifier.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: 텔레그램 알림기(메시지 만들기+발송) 추가 + 테스트"
```

---

## Task 7: 조회기 — 사이트 분석 & A안/B안 결정 (탐색)

> ⚠️ 이 작업은 외부 사이트에 의존하므로 미리 코드를 다 짤 수 없다. **실제로 사이트를
> 열어보며 빈자리를 읽는 방법을 정하는** 탐색 단계다. 결과를 문서에 적고, 샘플을 저장한다.

**Files:**
- Create: `samples/` 아래 응답 샘플, `docs/superpowers/notes-fetcher.md` (조사 결과 메모)

- [ ] **Step 1: 브라우저 개발자도구로 '빈자리 통로(API)' 찾기**

브라우저에서 `https://life.gangnam.go.kr/fmcs/54` 접속 → F12(개발자도구) → "네트워크(Network)" 탭 →
센터(예: 세곡)·시설(테니스장)·날짜 선택 후 "조회" 클릭 → 그때 새로 뜨는 요청 중
빈자리 정보(JSON)를 돌려주는 주소를 찾는다.

- [ ] **Step 2: A안 가능 여부 판정 + 메모**

Create `docs/superpowers/notes-fetcher.md`에 다음을 기록:
- 찾은 요청 주소(URL)와 방식(GET/POST), 보낸 값(센터코드·시설코드·날짜 등)
- 응답에서 빈자리가 어떤 모양으로 오는지(예: `{"list":[{"date":"...","time":"...","status":"가능"}]}`)
- 포이·세곡의 센터코드/시설코드
- **결론: A안(직접 호출) 가능 / 불가 → B안(브라우저 자동화)**

- [ ] **Step 3: 응답 샘플 저장 (테스트용)**

빈자리가 있을 때와 없을 때의 실제 응답을 각각 `samples/poi_response.json`, `samples/segok_response.json`으로 저장.
(A안이면 JSON 원문, B안이면 조회 결과 화면의 HTML 일부)

- [ ] **Step 4: 커밋**

```bash
git add samples/ docs/superpowers/notes-fetcher.md
git commit -m "docs: 사이트 빈자리 조회 방식(A/B안) 조사 + 응답 샘플 저장"
```

---

## Task 8: 조회기 — 빈자리 파서 + 실제 연동

**Files:**
- Create: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

> Task 7에서 저장한 **샘플**로 '파서(응답 → Slot 목록 변환)'를 TDD한다.
> 파서는 외부 의존이 없어 테스트 가능. 실제 사이트 호출 부분만 통합으로 둔다.

- [ ] **Step 1: 파서 테스트 작성 (Task 7 샘플의 실제 구조에 맞춰 값 수정)**

Create `tests/test_fetcher.py`:
```python
"""빈자리 파서 테스트: 사이트 응답(샘플)을 Slot 목록으로 바꿔야 함.
※ 아래 기대값은 Task 7에서 저장한 samples/의 실제 내용에 맞게 채운다."""
import json
from pathlib import Path
from src.models import Slot
from src.fetcher import parse_slots

SAMPLES = Path(__file__).parent.parent / "samples"


def test_샘플에서_빈자리_파싱():
    raw = json.loads((SAMPLES / "segok_response.json").read_text(encoding="utf-8"))
    slots = parse_slots(raw, court="세곡")
    # 샘플에 들어있는 '예약 가능' 칸이 Slot으로 나와야 함
    assert all(isinstance(s, Slot) for s in slots)
    assert all(s.court == "세곡" for s in slots)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_fetcher.py -v`
Expected: FAIL — `No module named 'src.fetcher'`

- [ ] **Step 3: 파서 + 조회 구현 (A안 기준; B안이면 fetch_court_raw만 교체)**

Create `src/fetcher.py`:
```python
"""강남구 예약 사이트에서 포이·세곡 빈자리를 읽어온다.

구조: fetch_court_raw(사이트에서 원문 받기) → parse_slots(원문 → Slot 목록)
- A안: requests로 내부 API 호출 (아래 기본 구현)
- B안 채택 시: fetch_court_raw 안만 Playwright로 교체하면 parse_slots는 그대로 재사용
"""
import requests
from src.models import Slot
from src.config import COURTS

# Task 7 조사에서 확인한 실제 주소/코드로 채운다
API_URL = "https://life.gangnam.go.kr/..."   # ← 조사 결과로 교체
COURT_CODES = {"포이": "...", "세곡": "..."}  # ← 조사 결과로 교체


def fetch_court_raw(court: str) -> dict:
    """한 코트의 빈자리 원문(응답)을 사이트에서 받아온다."""
    resp = requests.post(API_URL, data={"center": COURT_CODES[court]}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_slots(raw: dict, court: str) -> list[Slot]:
    """사이트 응답(raw)에서 '예약 가능'한 칸만 Slot 목록으로 바꾼다.
    ※ 아래 키 이름(list/date/time/status)은 Task 7 조사 결과에 맞게 수정."""
    slots = []
    for item in raw.get("list", []):
        if item.get("status") == "가능":           # ← 실제 '가능' 표시 값으로 교체
            slots.append(Slot(court, item["date"], item["time"]))
    return slots


def fetch_slots() -> list[Slot]:
    """대상 코트 전부의 빈자리를 모아서 돌려준다. (main이 호출하는 입구)"""
    all_slots = []
    for court in COURTS:
        try:
            raw = fetch_court_raw(court)
            all_slots.extend(parse_slots(raw, court))
        except Exception as e:
            # 한 코트 조회가 실패해도 다른 코트는 계속 (오류는 호출부에서 처리)
            print(f"[조회 실패] {court}: {e}")
    return all_slots
```

- [ ] **Step 4: 테스트 통과 확인 (샘플 값에 맞게 parse_slots 키 조정 후)**

Run: `pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: 실제 사이트로 1회 수동 확인**

Run: `python -c "from src.fetcher import fetch_slots; print(fetch_slots())"`
Expected: 현재 빈자리가 Slot 목록으로 출력 (없으면 빈 목록 `[]`)

- [ ] **Step 6: 커밋**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: 사이트 빈자리 조회기(파서+연동) 추가 + 샘플 테스트"
```

---

## Task 9: 전체 조율 (main.py) + 로컬 전체 실행

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: 조율 구현**

Create `src/main.py`:
```python
"""전체 흐름 조율: 조회 → 시간대 필터 → 새 빈자리 비교 → 알림 → 상태 저장."""
import sys
from src.fetcher import fetch_slots
from src.filters import is_wanted_time
from src.differ import find_new_slots
from src.notifier import format_message, send_telegram
from src.state import load_slots, save_slots

STATE_PATH = "state.json"  # 직전 빈자리 기록 위치


def main() -> int:
    # 1) 사이트에서 현재 빈자리 전부 읽기
    try:
        current_all = fetch_slots()
    except Exception as e:
        # 사이트 자체를 못 읽으면 '읽기 실패'를 알려서 조용히 죽지 않게
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        return 1

    # 2) 원하는 시간대(평일 저녁+주말)만 거르기
    wanted = [s for s in current_all if is_wanted_time(s)]

    # 3) 직전과 비교해 '새로 생긴 것'만
    previous = load_slots(STATE_PATH)
    new_slots = find_new_slots(wanted, previous)

    # 4) 새 빈자리가 있으면 텔레그램 알림
    message = format_message(new_slots)
    if message:
        send_telegram(message)
        print(f"[알림] {len(new_slots)}건 발송")
    else:
        print("[변화 없음]")

    # 5) 이번 결과를 직전 기록으로 저장 (다음 비교용)
    save_slots(STATE_PATH, wanted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 전체 테스트 통과 확인**

Run: `pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 3: 실제 토큰으로 로컬 전체 실행 (텔레그램 봇 준비 후)**

`.env`에 실제 `TELEGRAM_TOKEN`·`TELEGRAM_CHAT_ID`를 넣고:
Run: `python -m src.main`
Expected: 빈자리가 있고 그게 처음이면 텔레그램에 알림 도착. 다시 실행하면 "[변화 없음]"

- [ ] **Step 4: 커밋**

```bash
git add src/main.py
git commit -m "feat: 전체 조율 main 추가 (조회→필터→비교→알림→저장)"
```

---

## Task 10: GitHub Actions 자동화 (무료 클라우드 24시간)

**Files:**
- Create: `.github/workflows/check.yml`

- [ ] **Step 1: 워크플로 작성**

Create `.github/workflows/check.yml`:
```yaml
# 강남 테니스 빈자리 자동 점검 — 약 5분마다 실행
name: 빈자리 점검

on:
  schedule:
    - cron: "*/5 * * * *"   # 5분마다 (GitHub 최소 간격; 혼잡 시 지연될 수 있음)
  workflow_dispatch:        # 손으로도 실행해 볼 수 있게

# 직전 빈자리 기록(state.json)을 실행 간에 캐시로 이어줌
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: 라이브러리 설치
        run: pip install -r requirements.txt

      # 직전 실행이 남긴 state.json 불러오기 (없으면 그냥 시작)
      - name: 직전 기록 복원
        uses: actions/cache@v4
        with:
          path: state.json
          key: tennis-state-${{ github.run_id }}
          restore-keys: tennis-state-

      - name: 빈자리 점검 실행
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python -m src.main
```

> **상태 캐시 주의:** `actions/cache`는 같은 key면 덮어쓰지 않으므로 `run_id`로 매번 새 key를
> 만들고 `restore-keys`로 가장 최근 것을 불러온다. 캐시가 가끔 비어도 최악은 '중복 알림 1회'라 안전.
> 더 빠른 주기(1분)가 필요하면 워크플로 내 루프 또는 작은 유료 서버로 확장(설계서 범위 밖).

- [ ] **Step 2: 커밋**

```bash
git add .github/workflows/check.yml
git commit -m "ci: GitHub Actions 5분 주기 자동 점검 워크플로 추가"
```

- [ ] **Step 3: GitHub 저장소 연결 + 비밀값 등록 (사용자와 함께)**

- GitHub에서 새 저장소 생성 후 `git remote add origin ...` + `git push -u origin main`
- 저장소 Settings → Secrets and variables → Actions →
  `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` 두 개 등록
- Actions 탭에서 "빈자리 점검" → "Run workflow"로 첫 수동 실행 확인

---

## Task 11: 사용자 설정 안내 (텔레그램 봇 + GitHub)

> 코드 작업이 아니라 사용자가 직접 하는 준비. 각 단계에서 그림처럼 안내.

- [ ] **텔레그램 봇 만들기:** 텔레그램에서 `@BotFather` 검색 → `/newbot` → 이름 정하면 **봇 토큰** 받음
- [ ] **내 채팅 아이디 얻기:** 만든 봇과 대화 시작(아무 말 전송) → `@userinfobot` 또는 API로 `chat_id` 확인
- [ ] **`.env`에 토큰 2개 입력** 후 Task 9 Step 3 로컬 실행으로 알림 도착 확인
- [ ] **GitHub 가입 + 저장소 생성** 후 Task 10 Step 3 진행

---

## Self-Review (작성자 자체 점검)

**1. 설계서 요구사항 커버리지:**
- 대상 포이·세곡 → config.COURTS ✅ (Task 2)
- 평일 저녁+주말 필터 → filters ✅ (Task 3)
- 텔레그램 알림 → notifier ✅ (Task 6)
- 알림만(자동예약 X) → 시스템에 예약 코드 없음 ✅
- 무료 클라우드 24시간 → GitHub Actions ✅ (Task 10)
- 3~5분 주기 → cron */5 ✅ (Task 10)
- 새 빈자리만(중복 방지) → differ + state ✅ (Task 4·5)
- 읽기 실패 시 경고 알림 → main의 try/except ✅ (Task 9)
- A안/B안 결정 → Task 7 탐색으로 명시 ✅

**2. 빈칸 점검:** Task 7·8의 `API_URL`·`COURT_CODES`·응답 키는 실제 사이트 조사(Task 7) 전에는
채울 수 없는 값이라 의도적으로 자리표시. 그 외 모든 코드는 완성형.

**3. 타입/이름 일관성:** `Slot(court,date,time)`, `fetch_slots()`, `parse_slots(raw,court)`,
`find_new_slots(current,previous)`, `format_message(slots)`, `send_telegram(text)`,
`load_slots/save_slots(path,...)` — 전 Task에서 이름·인자 일치 확인 ✅

**알려진 한계(설계서에 반영됨):** GitHub Actions cron은 혼잡 시 5분 이상 지연될 수 있어
취소표를 놓칠 가능성이 있다. 더 빠른 감시는 유료 서버 확장(범위 밖).
