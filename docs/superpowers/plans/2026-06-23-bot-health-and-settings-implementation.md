# 봇 고장 알림 + 설정표 직접 조정 — 구현 공정표

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 봇이 멈추거나 일부 실패하면 텔레그램으로 알리고, 시설 켜고끄기·시간대를 코드 수정 없이 `settings.yaml`로 직접 조정하게 한다.

**Architecture:** 하드코딩된 시간대/시설을 사람이 읽는 설정표(`settings.yaml`)로 빼고, 봇이 매 실행 시 읽어 적용한다(형식 오류는 폴백으로 보호). 시간대 판별은 시설 설정 dict를 받는 범용 함수 하나로 통일. 완전 멈춤은 외부 감시(healthchecks.io) 핑, 일부 실패는 매일 요약에 한 줄로 보고.

**Tech Stack:** Python 3.13, requests, **PyYAML(신규)**, pytest, GitHub Actions(cron), healthchecks.io.

**전제(설계서):** `docs/superpowers/specs/2026-06-23-bot-health-and-settings-design.md`

---

## 파일 구조

| 파일 | 책임 | 변경 |
|---|---|---|
| `settings.yaml` | 사용자가 고치는 설정표 | 신규 |
| `settings.last_good.yaml` | 직전 정상 설정 백업(자동 생성, gitignore) | 신규(런타임) |
| `src/settings_loader.py` | 설정표 읽기·검증·폴백·기본값 | 신규 |
| `src/filters.py` | 설정 기반 범용 시간 필터로 통일 | 수정 |
| `src/esongpa.py` | 시설 on/off + 설정 기반 필터 사용 | 수정 |
| `src/main.py` | 설정 적용, 실패 기록, 요약에 실패 보고, 설정오류 알림 | 수정 |
| `src/notifier.py` | 요약에 "어제 실패" 줄 추가 | 수정 |
| `src/state.py` | 실패 카운트 저장/불러오기 | 수정 |
| `.github/workflows/check.yml` | 끝에 healthchecks "살아있어" 핑 | 수정 |
| `requirements.txt` | PyYAML 추가 | 수정 |
| `.gitignore` | `settings.last_good.yaml` 추가 | 수정 |
| `tests/test_settings_loader.py` | 읽기·검증·폴백 테스트 | 신규 |
| `tests/test_filters.py` | 범용 필터 테스트 | 수정 |
| `tests/test_notifier.py` | 요약 실패줄 테스트 | 수정 |

> 봇 본체(fetcher·differ·조회·발송)는 손대지 않는다. "설정을 어디서 읽나"와 "고장 알림"만 더한다.

---

## Task 1: PyYAML 의존성 + 설정표 정상 읽기

**Files:** Modify `requirements.txt` / Create `src/settings_loader.py`, `tests/test_settings_loader.py`

- [ ] **Step 1: requirements.txt에 PyYAML 추가**

```
requests>=2.31
python-dotenv>=1.0
pytest>=8.0
PyYAML>=6.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: 실패 테스트 작성**

```python
# tests/test_settings_loader.py
"""설정표 읽기·검증·폴백 — 사용자가 틀려도 봇이 안 멈추게."""
from src.settings_loader import load_settings, validate_settings, DEFAULT_SETTINGS


def test_정상_설정표를_읽는다(tmp_path):
    p = tmp_path / "settings.yaml"
    p.write_text("강남:\n  받기: true\n  매일: [19, 20]\n", encoding="utf-8")
    settings, err = load_settings(str(p), str(tmp_path / "lg.yaml"))
    assert err is None
    assert settings["강남"]["받기"] is True
    assert settings["강남"]["매일"] == [19, 20]


def test_파일_없으면_기본값(tmp_path):
    settings, err = load_settings(str(tmp_path / "none.yaml"), str(tmp_path / "lg.yaml"))
    assert err is None
    assert settings == DEFAULT_SETTINGS
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `pytest tests/test_settings_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.settings_loader'`

- [ ] **Step 4: settings_loader.py 작성(정상 읽기 + 기본값)**

```python
# src/settings_loader.py
"""설정표(settings.yaml) 읽기 + 검증 + 폴백.

사용자가 settings.yaml을 고쳐도 형식이 틀리면 봇이 멈추지 않게,
직전 정상 설정 백업 또는 코드 내장 기본값으로 폴백한다.
"""
from pathlib import Path

import yaml

# 코드 내장 기본값(설정표 없거나 첫 실행 시) — 현재 운영 시간대와 동일
DEFAULT_SETTINGS = {
    "강남": {"받기": True, "매일": [19, 20, 21]},
    "송파": {"받기": True, "토": [8, 10]},
    "잠실": {"받기": True, "토": [18, 20], "일": [18, 20],
             "월": [20], "화": [20], "수": [20]},
}

WEEKDAY_KEYS = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday() 0~6


def validate_settings(data):
    """설정 dict가 올바른 형식인지 검사. 틀리면 ValueError를 던진다."""
    if not isinstance(data, dict):
        raise ValueError("설정표 최상위가 시설 목록(표)이 아닙니다")
    for fac, cfg in data.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"'{fac}' 설정이 표 형식이 아닙니다")
        if not isinstance(cfg.get("받기"), bool):
            raise ValueError(f"'{fac}'의 '받기'는 true 또는 false여야 합니다")
        for key, val in cfg.items():
            if key == "받기":
                continue
            if key not in WEEKDAY_KEYS and key != "매일":
                raise ValueError(f"'{fac}'의 '{key}'는 요일(월~일) 또는 '매일'이어야 합니다")
            if not (isinstance(val, list) and all(isinstance(h, int) for h in val)):
                raise ValueError(f"'{fac} {key}'의 시간은 숫자 목록이어야 합니다(예: [19, 20])")
    return data


def load_settings(path="settings.yaml", last_good="settings.last_good.yaml"):
    """설정표를 읽어 (검증된 dict, 오류메시지 or None) 반환. 다음 Task에서 폴백 보강."""
    p = Path(path)
    if not p.exists():
        return DEFAULT_SETTINGS, None
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    validate_settings(data)
    Path(last_good).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return data, None
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_settings_loader.py -v`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt src/settings_loader.py tests/test_settings_loader.py
git commit -m "feat: 설정표(settings.yaml) 읽기 + 기본값 (PyYAML)"
```

---

## Task 2: 설정표 형식 오류 폴백

**Files:** Modify `src/settings_loader.py`, `tests/test_settings_loader.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
# tests/test_settings_loader.py 에 추가
import pytest


def test_받기가_불린_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": "응", "매일": [19]}})


def test_시간이_숫자목록_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": True, "매일": "저녁"}})


def test_형식틀리면_직전정상으로_폴백(tmp_path):
    good = tmp_path / "lg.yaml"
    good.write_text("강남:\n  받기: true\n  매일: [19]\n", encoding="utf-8")
    bad = tmp_path / "settings.yaml"
    bad.write_text("강남:\n  받기: 이상한값\n", encoding="utf-8")  # 형식 오류
    settings, err = load_settings(str(bad), str(good))
    assert err is not None and "형식 오류" in err
    assert settings["강남"]["매일"] == [19]  # 직전 정상 사용


def test_직전정상도_없으면_기본값(tmp_path):
    bad = tmp_path / "settings.yaml"
    bad.write_text("강남:\n  받기: 이상한값\n", encoding="utf-8")
    settings, err = load_settings(str(bad), str(tmp_path / "none.yaml"))
    assert err is not None
    assert settings == DEFAULT_SETTINGS
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_settings_loader.py -v`
Expected: FAIL (폴백 미구현 — 오류 시 예외가 그대로 터짐)

- [ ] **Step 3: load_settings에 폴백 추가**

`load_settings`의 본문을 try/except로 감싼다:

```python
def load_settings(path="settings.yaml", last_good="settings.last_good.yaml"):
    """설정표를 읽어 (검증된 dict, 오류메시지 or None) 반환.

    형식 오류 시: 직전 정상 설정 → 없으면 기본값. 봇은 멈추지 않는다.
    """
    p = Path(path)
    if not p.exists():
        return DEFAULT_SETTINGS, None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        validate_settings(data)
        Path(last_good).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        return data, None
    except Exception as e:
        lg = Path(last_good)
        if lg.exists():
            try:
                good = validate_settings(yaml.safe_load(lg.read_text(encoding="utf-8")))
                return good, f"설정표 형식 오류({e}). 직전 정상 설정으로 작동합니다."
            except Exception:
                pass
        return DEFAULT_SETTINGS, f"설정표 형식 오류({e}). 기본 설정으로 작동합니다."
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_settings_loader.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/settings_loader.py tests/test_settings_loader.py
git commit -m "feat: 설정표 형식 오류 시 직전정상/기본값 폴백"
```

---

## Task 3: settings.yaml 실물 + gitignore

**Files:** Create `settings.yaml` / Modify `.gitignore`

- [ ] **Step 1: settings.yaml 작성(현재 운영과 동일하게 시작)**

```yaml
# ───────────────────────────────────────
#  🎾 테니스 알림 설정표
#  이 표를 고치면 다음 점검(최대 5분)부터 반영됩니다.
#  · 받기: true(알림 받기) / false(끄기)
#  · 시간: 시작 시각 숫자만 — 20 = 저녁 8시
# ───────────────────────────────────────

강남:                      # 포이·세곡
  받기: true
  매일: [19, 20, 21]       # 저녁 7·8·9시

송파:
  받기: true
  토: [8, 10]              # 토요일 오전 8·10시

잠실:                      # 2시간 단위 시설
  받기: true               # ← 잠깐 끄려면 false 로만 바꾸면 끝
  토: [18, 20]
  일: [18, 20]
  월: [20]
  화: [20]
  수: [20]
```

- [ ] **Step 2: .gitignore에 백업파일 추가**

`.gitignore` 끝에 추가:
```
# 설정표 직전 정상 백업(런타임 자동 생성)
settings.last_good.yaml
```

- [ ] **Step 3: 커밋**

```bash
git add settings.yaml .gitignore
git commit -m "feat: 설정표 실물(settings.yaml) 추가(현재 시간대와 동일)"
```

---

## Task 4: 설정 기반 범용 시간 필터

**Files:** Modify `src/filters.py`, `tests/test_filters.py`

> 기존 `is_wanted_time`/`is_songpa_wanted`/`is_jamsil_wanted` 세 함수를 **시설 설정 dict를 받는 범용 함수 `is_wanted_for` 하나로** 통일한다. 호출부(Task 5)도 함께 바꾼다.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_filters.py — 잠실/송파/강남 케이스를 is_wanted_for로 재작성
from src.filters import is_wanted_for
from src.models import Slot

# 요일 확정: 2026-07-04=토, 05=일, 06=월, 07=화, 01·08=수, 02=목, 03=금
강남 = {"받기": True, "매일": [19, 20, 21]}
송파 = {"받기": True, "토": [8, 10]}
잠실 = {"받기": True, "토": [18, 20], "일": [18, 20], "월": [20], "화": [20], "수": [20]}


def test_강남_매일_저녁():
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "20:00"), 강남) is True  # 월요일
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "18:00"), 강남) is False


def test_송파_토요일만():
    assert is_wanted_for(Slot("송파", "x", "2026-07-04", "08:00"), 송파) is True   # 토
    assert is_wanted_for(Slot("송파", "x", "2026-07-01", "08:00"), 송파) is False  # 수


def test_잠실_주말18_20_평일월화수20():
    assert is_wanted_for(Slot("잠실", "x", "2026-07-04", "18:00"), 잠실) is True   # 토 18
    assert is_wanted_for(Slot("잠실", "x", "2026-07-06", "20:00"), 잠실) is True   # 월 20
    assert is_wanted_for(Slot("잠실", "x", "2026-07-06", "18:00"), 잠실) is False  # 월 18 제외
    assert is_wanted_for(Slot("잠실", "x", "2026-07-02", "20:00"), 잠실) is False  # 목 제외


def test_받기_false면_무조건_제외():
    꺼짐 = {"받기": False, "매일": [19, 20, 21]}
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "20:00"), 꺼짐) is False
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_filters.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_wanted_for'`

- [ ] **Step 3: filters.py를 범용 함수로 교체**

```python
# src/filters.py
"""원하는 시간대 빈자리만 골라내는 필터 (설정표 기반)."""
from datetime import date
from src.models import Slot
from src.settings_loader import WEEKDAY_KEYS


def is_wanted_for(slot: Slot, fac_cfg: dict) -> bool:
    """이 빈자리가 해당 시설 설정(fac_cfg)상 알림 대상인지.

    fac_cfg 예: {"받기": True, "매일": [19,20,21]} 또는
                {"받기": True, "토": [18,20], "월": [20], ...}
    - 받기=False면 무조건 제외
    - 그 날 요일에 해당하는 시간 목록(없으면 '매일')에 시작시각이 있으면 대상
    """
    if not fac_cfg.get("받기"):
        return False
    y, m, d = (int(x) for x in slot.date.split("-"))
    day_key = WEEKDAY_KEYS[date(y, m, d).weekday()]
    hours = fac_cfg.get(day_key, fac_cfg.get("매일", []))
    return int(slot.time.split(":")[0]) in hours
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_filters.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/filters.py tests/test_filters.py
git commit -m "refactor: 시간 필터를 설정 기반 범용 is_wanted_for로 통일"
```

---

## Task 5: main·esongpa가 설정표를 쓰게 연결

**Files:** Modify `src/esongpa.py`, `src/main.py`

> esongpa의 `ESONGPA_SITES`에서 `wanted` 함수를 제거하고, `fetch_esongpa_slots(settings)`가 시설별 설정으로 on/off + 필터하게 한다. main은 설정을 읽어 강남/esongpa에 넘기고, 설정 오류는 텔레그램으로 알린다.

- [ ] **Step 1: esongpa.py 수정**

`ESONGPA_SITES`에서 `wanted` 키 제거(주소·페이지만 남김), import에서 필터 제거:

```python
# src/esongpa.py 상단 import 교체
from src.models import Slot
from src.filters import is_wanted_for

# ESONGPA_SITES — wanted 제거
ESONGPA_SITES = [
    {"center": "송파", "base": "https://spc.esongpa.or.kr", "list_page": "s05.od.list.php"},
    {"center": "잠실", "base": "https://club.esongpa.or.kr", "list_page": "s07.od.list.php"},
]
```

`fetch_esongpa_slots`를 settings 인자 받게 교체:

```python
def fetch_esongpa_slots(settings):
    """등록된 esongpa 시설의 빈자리(설정 기반 on/off + 시간필터)를 Slot 목록으로.

    settings: {"송파": {...}, "잠실": {...}} 형태. 받기=False인 시설은 건너뜀.
    ID/비번 미설정이면 빈 목록. 한 시설 실패는 건너뜀.
    """
    if not (os.environ.get("SONGPA_ID") and os.environ.get("SONGPA_PW")):
        return []
    now = datetime.now(KST)
    result = []
    for site in ESONGPA_SITES:
        cfg = settings.get(site["center"])
        if not cfg or not cfg.get("받기"):
            continue  # 설정표에서 끈 시설은 조회 안 함
        try:
            session = requests.Session()
            session.headers.update(HEADERS)
            if not _login(session, site["base"]):
                raise RuntimeError(f"{site['center']} 로그인 실패 (ID/비번 확인)")
            for ym in _months(now.date()):
                url = site["base"] + "/page/rent/" + site["list_page"]
                r = session.get(url, params={"sch_sym": ym}, verify=False, timeout=20)
                for slot in parse_esongpa(r.text, site["center"]):
                    slot_dt = datetime.strptime(slot.date + slot.time, "%Y-%m-%d%H:%M").replace(tzinfo=KST)
                    if slot_dt > now and is_wanted_for(slot, cfg):
                        result.append(slot)
        except Exception as e:
            print(f"[{site['center']} 조회 실패] {e}")
    return result
```

- [ ] **Step 2: main.py 수정(설정 읽기·적용·오류알림)**

import에 추가: `from src.settings_loader import load_settings`, `from src.filters import is_wanted_for`
(`is_wanted_time` import 제거)

`run_vacancy_alert` 교체:

```python
def run_vacancy_alert():
    """① 빈자리/취소표 알림."""
    settings, err = load_settings()
    if err:
        send_telegram(f"⚠️ {err}")
    try:
        current_all = fetch_slots()
    except Exception as e:
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        print(f"[읽기 실패] {e}")
        return

    강남cfg = settings.get("강남", {})
    wanted = [s for s in current_all if is_wanted_for(s, 강남cfg)]
    try:
        wanted += fetch_esongpa_slots(settings)
    except Exception as e:
        print(f"[esongpa 조회 실패] {e}")

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
```

`run_summary`도 settings 사용하게 교체:

```python
def run_summary():
    """매일 1회: 현재 '원하는 시간대' 빈자리 전체 요약 + 어제 실패 보고."""
    settings, err = load_settings()
    if err:
        send_telegram(f"⚠️ {err}")
    강남cfg = settings.get("강남", {})
    wanted = []
    try:
        wanted += [s for s in fetch_slots() if is_wanted_for(s, 강남cfg)]
    except Exception as e:
        print(f"[요약-강남 조회 실패] {e}")
    try:
        wanted += fetch_esongpa_slots(settings)
    except Exception as e:
        print(f"[요약-esongpa 조회 실패] {e}")
    send_telegram(format_summary(wanted))  # 실패보고는 Task 6에서 합침
    print(f"[요약 발송] {len(wanted)}건")
```

- [ ] **Step 3: 전체 테스트(회귀)**

Run: `pytest -v`
Expected: PASS (기존 + 새 테스트). esongpa 격리 테스트가 `fetch_esongpa_slots()` 인자 변경으로 깨지면 `fetch_esongpa_slots(DEFAULT_SETTINGS)`로 수정.

- [ ] **Step 4: 로컬 실행 확인(로그인정보 없이 크래시 없는지)**

Run: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m src.main`
Expected: 크래시 없이 `[빈자리 ...]` 출력(강남만, esongpa는 빈 목록)

- [ ] **Step 5: 커밋**

```bash
git add src/esongpa.py src/main.py
git commit -m "feat: main·esongpa가 설정표(시설 on/off+시간대)를 사용"
```

---

## Task 6: 일부 실패 기록 + 매일 요약에 보고

**Files:** Modify `src/state.py`, `src/notifier.py`, `src/main.py`, `tests/test_notifier.py`

- [ ] **Step 1: state.py에 실패 카운트 저장/불러오기 추가**

```python
# src/state.py 에 추가
def load_failures(path) -> dict:
    """시설별 실패 횟수 dict. 파일 없으면 빈 dict."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_failures(path, failures: dict) -> None:
    """시설별 실패 횟수 dict 저장."""
    Path(path).write_text(json.dumps(failures, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 2: notifier 요약에 실패줄 — 실패 테스트**

```python
# tests/test_notifier.py 에 추가
from src.notifier import format_summary


def test_요약에_실패보고_붙는다():
    msg = format_summary([], failures={"잠실": 3})
    assert "현재 빈자리 없음" in msg
    assert "잠실" in msg and "3" in msg and "실패" in msg


def test_실패없으면_실패줄_없음():
    msg = format_summary([], failures={})
    assert "실패" not in msg
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL — `format_summary() got unexpected keyword argument 'failures'`

- [ ] **Step 4: format_summary에 failures 인자 추가**

```python
# src/notifier.py 의 format_summary 교체
def format_summary(slots: list[Slot], failures: dict | None = None) -> str:
    """매일 1회 '현재 빈자리 전체' 요약. 빈 목록이면 '없음'. 어제 실패 있으면 한 줄 덧붙임."""
    if not slots:
        lines = ["🎾 [오늘의 빈자리 현황]", "현재 빈자리 없음"]
    else:
        lines = ["🎾 [오늘의 빈자리 현황]"]
        for s in sorted(slots, key=lambda x: (x.court, x.date, x.time)):
            lines.append(f"🏟 {s.court} {s.place}  📅 {s.date} {s.time}")
        lines.append(f"👉 예약: {RESERVE_URL}")
    if failures:
        detail = ", ".join(f"{k} {v}번" for k, v in failures.items())
        lines.append(f"⚠️ 어제 조회 실패: {detail}")
    return "\n".join(lines)
```

- [ ] **Step 5: 통과 확인**

Run: `pytest tests/test_notifier.py -v`
Expected: PASS

- [ ] **Step 6: main에서 실패 기록·요약 반영**

`run_vacancy_alert`의 esongpa 실패 지점에서 카운트. 상단 import에 `load_failures, save_failures` 추가, `FAIL_PATH = "failures.json"` 상수 추가.

`fetch_esongpa_slots`가 실패 시설을 알려주도록 — 간단히 main에서 강남/esongpa try/except에 카운트 누적:

```python
# run_vacancy_alert 내 esongpa 블록 교체
    failures = load_failures(FAIL_PATH)
    try:
        esongpa_slots = fetch_esongpa_slots(settings)
        wanted += esongpa_slots
    except Exception as e:
        failures["esongpa"] = failures.get("esongpa", 0) + 1
        print(f"[esongpa 조회 실패] {e}")
    save_failures(FAIL_PATH, failures)
```

`run_summary` 마지막 교체(요약에 실패 싣고 리셋):

```python
    failures = load_failures(FAIL_PATH)
    send_telegram(format_summary(wanted, failures=failures))
    save_failures(FAIL_PATH, {})  # 보고 후 리셋
    print(f"[요약 발송] {len(wanted)}건, 실패 {sum(failures.values())}건")
```

> 주의: `check.yml` 캐시 경로에 `failures.json` 추가(Task 7에서).

- [ ] **Step 7: 전체 테스트**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 8: 커밋**

```bash
git add src/state.py src/notifier.py src/main.py tests/test_notifier.py
git commit -m "feat: 일부 실패를 기록해 매일 아침 요약에 보고"
```

---

## Task 7: healthchecks "살아있어" 핑 + 캐시 경로 + 가입 안내

**Files:** Modify `.github/workflows/check.yml` / Create `docs/healthchecks-setup.md`

- [ ] **Step 1: check.yml 캐시 경로에 failures.json 추가**

`직전 기록 복원` 스텝의 `path:`에 한 줄 추가:
```yaml
          path: |
            state.json
            status.json
            failures.json
```

- [ ] **Step 2: check.yml 끝에 healthchecks 핑 스텝 추가**

```yaml
      # 봇이 한 바퀴 정상 완료했음을 외부 감시(healthchecks.io)에 알림.
      # 이 신호가 약 10분 끊기면 healthchecks.io가 텔레그램으로 "봇 멈춤" 알림.
      - name: 살아있어 신호(healthchecks)
        if: always()   # 조회가 일부 실패해도 '봇은 살아있음'은 보냄
        run: |
          if [ -n "${{ secrets.HC_PING_URL }}" ]; then
            curl -fsS -m 10 --retry 3 "${{ secrets.HC_PING_URL }}" || true
          fi
```

- [ ] **Step 3: healthchecks 가입 안내 문서 작성**

```markdown
# docs/healthchecks-setup.md
# 봇 멈춤 감지(healthchecks.io) 설정 — 1회

1. https://healthchecks.io 가입(무료, 구글 로그인 가능)
2. "Add Check" → 이름 '테니스봇', Period 5분, Grace 10분 정도로 설정
3. 그 체크의 **Ping URL** 복사
4. GitHub 저장소 → Settings → Secrets and variables → Actions → New secret
   - 이름 `HC_PING_URL`, 값 = 복사한 Ping URL
5. healthchecks.io 체크 → Integrations → Telegram 연결
   (또는 webhook integration에 텔레그램 sendMessage URL 등록 — 봇 토큰 재사용)
6. 끝. 봇이 10분 넘게 신호를 못 보내면 텔레그램으로 "🚨 봇 멈춤" 알림이 옵니다.
```

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/check.yml docs/healthchecks-setup.md
git commit -m "feat: healthchecks 살아있어 핑 + 가입 안내(완전 멈춤 감지)"
```

---

## Task 8: 통합 검증 & 배포 준비

- [ ] **Step 1: 전체 테스트 + 로컬 실행**

Run: `pytest -v` → 전체 PASS
Run: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m src.main` → 크래시 없음
Run: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m src.main summary` → 요약 동작

- [ ] **Step 2: 변경 요약 + 사용자 승인(규칙 D)**

바뀐 파일·동작을 쉬운 말로 보고하고 "1층(main)에 배포할까요?" 승인 요청.

- [ ] **Step 3: 승인 후 push + 배포 확인**

```bash
git log origin/main..HEAD --oneline   # 올라갈 커밋 확인
git push origin main
```
- 배포 후: healthchecks.io 가입·연동(docs/healthchecks-setup.md) 1회 수행
- `settings.yaml` 한 줄 바꿔보고(예: 잠실 받기 false) 다음 점검에 반영되는지 확인 후 원복

---

## Self-Review 메모(작성자 점검)
- **Spec 커버리지:** 설정표 읽기·검증·폴백(Task 1·2) / 실물(Task 3) / 범용 필터(Task 4) / main·esongpa 연결(Task 5) / 일부실패 보고(Task 6) / healthchecks 핑·안내(Task 7) — 모두 task 있음.
- **회귀 보호:** 매 task `pytest -v`. filters 통일 시 기존 잠실 규칙(주말18·20/월화수20) 동일 유지.
- **타입 일관성:** `is_wanted_for(slot, fac_cfg)`, `load_settings()→(dict, err)`, `format_summary(slots, failures)`, `load_failures/save_failures` 이름 전 task 일치. `WEEKDAY_KEYS`는 settings_loader 한 곳 정의·filters에서 import(중복 제거).
- **불확실성:** healthchecks↔텔레그램 연동은 가입 화면에서 진행(Task 7 안내). 무료 Telegram integration 막히면 webhook+봇토큰 방식으로.
