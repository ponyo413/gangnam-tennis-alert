# 대치유수지 테니스장 추가 — 설계서

> 작성일: 2026-06-24 (개정: 저빈도 조회 규칙 반영)
> 한 줄 요약: 강남·송파·잠실에 이어 **대치유수지 테니스장**의 빈자리(취소표)도
> 텔레그램으로 알려준다. 단, 사이트가 "매크로 빈번 접속 금지"를 공지했으므로
> **15분 간격 + 한국시간 08~24시에만** 조회하고, 그 사이엔 직전에 본 결과를 유지한다.

---

## 1. 목적

대치유수지 테니스장(`대치유수지.kr`)의 빈자리가 생기면 텔레그램으로 알림.
강남(포이·세곡)·송파·잠실과 **같은 봇·같은 알림창**에서 함께 본다.
**사이트 부담을 줄이기 위해 저빈도(15분, 주간만)로 조회**한다.

## 2. 확정 요구사항 (사용자 협의 완료)

| 항목 | 내용 |
|------|------|
| 감시 시간대(빈자리) | **평일(월~금) 19시** / **토요일 7·9·19시** / **일요일 없음** |
| 코트 | A·B·C **전부** (어느 코트든 비면 알림) |
| **조회 빈도** | **15분 간격** (봇 전체는 5분마다 돌지만 대치유수지는 15분에 1번만 실제 접속) |
| **조회 활동시간** | **KST 08:00~24:00에만** (새벽 00~08시는 접속 안 함) |
| 동작 | 읽기 전용 — **자동 예약 안 함** (강남과 동일) |
| 알림 | 기존 텔레그램 봇에 합류(별도 알림창 X) |

> **저빈도·시간창의 이유:** 사이트 공지 "매크로 사용자 IP 제한 안내"(2026.04.02) — 매크로 등
> 빈번한 IP 접속 시 IP 차단·이용 정지 가능. 5분마다 긁으면 이에 해당하므로, 접속을
> 15분 간격 + 주간으로 줄여(하루 약 64회) 부담과 위험을 낮춘다.
> (강남·송파·잠실은 별개 사이트이며 해당 공지 대상이 아니라 기존대로 둔다.)

> 시간은 2시간 단위 칸의 **시작 시각**이다. 19시 = `19:00~21:00`, 7시 = `07:00~09:00`.

## 3. 사이트 분석 결과 (실측)

- 조회 주소: `https://www.대치유수지.kr/?act=reservation.reservation_list&type=8&cyear=YYYY&cmonth=M`
  - `type=8` = 테니스장 (7=축구장 등 다른 종목)
  - 퓨니코드 도메인: `xn--vk1b79znxd34c61h.kr`
- **로그인 불필요** — 누구나 빈자리표를 볼 수 있음 (송파·잠실보다 쉬움, 강남과 같은 급)
- **서버 렌더링 HTML** — 빈자리 데이터가 페이지에 바로 들어있음 (JavaScript/AJAX 아님)
- **봇 차단(기술적)은 없음** — 정상 응답(HTTP 200). 단 위 공지처럼 빈번 접속은 정책상 제한.
- 시간대: **2시간 단위 7칸** — `07~09, 09~11, 11~13, 13~15, 15~17, 17~19, 19~21`
- 코트: **A·B·C 3개**
- 빈자리 표시:
  - `possible_icn_on.gif`(title="가능") = **빈자리**
  - `possible_icn_off.gif`(title="불가능") = 찼거나 막힘
- 빈자리 칸 구조(결정적):
  ```html
  <dt><a href="#" class="_rev" data-date="2026-07-01" data-time="0" data-type="9">
      <img src="/images/sub/possible_icn_on.gif" title="가능" /></a></dt>
  ```
  - `data-date` = 날짜(`YYYY-MM-DD`), `data-time` = 시간 인덱스(0~6)
  - **시작시각 = 7 + (data-time × 2)** → 0→07시, 1→09시 … 6→19시
  - 코트는 한 행(`<dl>`)의 `<dt>` **순서**(1번째=A, 2번째=B, 3번째=C)로 판별
  - 빈자리(`on`) 칸에만 `data-date`/`data-time`이 있고, 찬 칸엔 없음 → 빈자리만 깔끔히 추출

## 4. 접근법 — 전용 부품 신설 + 조회 게이트

봇은 "**시설군마다 자기 부품 하나**" 구조다.
- 강남(포이·세곡): `src/fetcher.py` (강남구청 REST API)
- 송파·잠실: `src/esongpa.py` (로그인 + HTML 파싱)

대치유수지는 사이트 방식이 위 둘과 모두 달라서(로그인 없는 Rhymix 계열 HTML),
**`src/daechi.py`** 를 새로 만들어 나란히 둔다.

저빈도(15분·주간)는 **조회 게이트**로 구현한다. 봇은 계속 5분마다 돌지만, 매 실행에서
"지금 대치유수지를 실제로 접속할 때인가?"(`is_daechi_due`)를 먼저 판단해서, 아니면
**직전에 본 빈자리를 그대로 유지**한다(접속 안 함). 이는 esongpa의 "닫힘 시 직전 유지"와
같은 발상이다 — 가짜 변동 알림을 막고 접속을 아낀다.

## 5. 컴포넌트 설계

### 5.1 `src/daechi.py` (신규)

**(a) `parse_daechi(html) -> list[Slot]`** — 빈자리 칸 추출(빈도와 무관, 순수 파싱)
- 각 `<dl>`(시간대 행)의 `<dt>` 1·2·3번째를 A·B·C 코트로 보고,
  `possible_icn_on` + `data-date`/`data-time`이 있는 칸만 빈자리로.
- `Slot(court="대치유수지", place="A코트"/"B코트"/"C코트", date, time)` (시각 = `7+idx*2`)

**(b) `fetch_daechi_slots(settings) -> list[Slot]`** — 실제 조회(순수, 게이트 모름)
- `받기=False`/설정 없음 → 빈 목록.
- **이번 달 + 다음 달** GET(로그인 없음) → `parse_daechi` → `is_wanted_for` + 미래만.
- 한 달 실패는 건너뜀. (호출 빈도는 main의 게이트가 통제하므로 이 함수는 빈도를 모른다.)

**(c) `is_daechi_due(now, last_fetch, interval_min=15) -> bool`** — 조회 게이트(순수함수)
- 상수: `ACTIVE_START_HOUR = 8`, `ACTIVE_END_HOUR = 24`, `FETCH_INTERVAL_MIN = 15`.
- 규칙:
  1. `now.hour`(KST)가 08~23시 밖이면(=새벽 0~7시) → `False` (접속 안 함)
  2. `last_fetch is None`(아직 한 번도 조회 안 함) → `True`
  3. `now - last_fetch >= 15분` → `True`, 아니면 `False`
- `now`는 KST aware datetime(`datetime.now(KST)`), `last_fetch`는 datetime 또는 None.
- read_fail_decision처럼 **판정만 떼어낸 순수함수**라 단위 테스트가 쉽다.

### 5.2 `settings.yaml` — 대치유수지 블록 추가

```yaml
대치유수지:
  받기: true        # 끄려면 false 로만 바꾸면 끝
  평일: [19]        # 월~금: 저녁 7시(19~21시)
  토: [7, 9, 19]    # 토요일: 오전 7·9시 + 저녁 7시
  # 일요일은 줄 없음 = 감시 안 함
```
> 빈도(15분)·시간창(08~24시)은 코드 상수로 고정한다(자주 바뀌지 않으므로 설정표에 넣지 않음).
> `settings.last_good.yaml`(백업본)은 다음 정상 실행 때 자동 갱신되므로 수동 수정 불필요.

### 5.3 `src/state.py` — 마지막 조회 시각 저장/로드 (신규 함수)

기존 `save_slots`/`load_slots`(Slot 목록 JSON)는 **대치유수지 직전 빈자리 저장에 그대로 재사용**.
추가로 마지막 조회 시각(ISO 문자열)만 저장:
```python
save_daechi_fetch_time(path, iso_str)   # {"at": "2026-06-24T14:30:00+09:00"}
load_daechi_fetch_time(path) -> str | None   # 없으면 None
```
(기존 `save_fail_count`/`load_fail_count`와 같은 작은 JSON 패턴)

### 5.4 `src/main.py` — 게이트 적용(조회 or 직전 유지)

`run_vacancy_alert()`에서 esongpa 다음, `save_failures` 전에:
```python
now = datetime.now(KST)
last_str = load_daechi_fetch_time(DAECHI_TIME_PATH)
last_dt = datetime.fromisoformat(last_str) if last_str else None
if is_daechi_due(now, last_dt):
    try:
        daechi_slots = fetch_daechi_slots(settings)      # 실제 접속(15분에 1번)
        save_slots(DAECHI_SLOTS_PATH, daechi_slots)       # 결과 박제
        save_daechi_fetch_time(DAECHI_TIME_PATH, now.isoformat())
        wanted += daechi_slots
    except Exception as e:
        failures["대치유수지"] = failures.get("대치유수지", 0) + 1
        wanted += load_slots(DAECHI_SLOTS_PATH)           # 실패 시 직전 유지
        print(f"[대치유수지 조회 실패] {e}")
else:
    wanted += load_slots(DAECHI_SLOTS_PATH)               # 시간창 밖/15분 미경과 → 직전 유지
```
`run_summary()`에서는 **새로 조회하지 않고** 저장된 직전 결과만 합류(접속 추가 절약):
```python
wanted += load_slots(DAECHI_SLOTS_PATH)
```
상수(`main.py` 상단): `DAECHI_SLOTS_PATH = "daechi_slots.json"`, `DAECHI_TIME_PATH = "daechi_fetch.json"`.
`KST`·`is_daechi_due`·`fetch_daechi_slots`는 `src.daechi`에서 import.

### 5.5 수정 불필요 확인(조사 완료)

- `settings_loader.py`: 시설명 화이트리스트가 **없음**(시간 키만 검증) → 대치유수지 추가만으로 통과. **수정 불필요.**
- `notifier.py`의 `format_summary`: `🏟 {court} {place} 📅 {date}(요일) {time}` 형식이라 대치유수지도 자동 표시. **수정 불필요.**

## 6. 데이터 흐름

```
(매 5분 실행) main: 지금 대치유수지 조회할 때인가? = is_daechi_due
   ├─ 예(08~24시 & 15분 경과): 페이지(이번달·다음달) GET
   │     → parse_daechi → is_wanted_for+미래 → 결과 박제(save_slots)+시각 기록
   └─ 아니오(새벽/15분 미경과/조회 실패): 박제된 직전 빈자리 그대로(load_slots, 접속 0)
   → (강남·송파·잠실과 합침) → differ: 직전과 달라졌으면 → 텔레그램 현황 1통
```

## 7. 저빈도 "직전 유지" (가짜 알림 방지)

대치유수지를 매 실행 조회하지 않으므로, 조회 안 하는 실행에서 빈자리를 0으로 두면
"있다 없다"가 깜빡여 가짜 변동 알림이 터진다. 그래서 조회하지 않는 실행에서는
**마지막으로 조회해 박제한 빈자리(`load_slots`)를 그대로** 합류시킨다.
(잠실의 "접수 닫힘 시 직전 유지"와 같은 목적·구조.)
- 미래 필터는 `fetch_daechi_slots`가 조회 시점에 이미 적용하므로, 박제된 목록은 그 시점 기준
  미래만 담긴다. 다음 조회(최대 15분 뒤)에 다시 정리되므로 과거 잔류는 최대 15분 수준.

## 8. 에러 처리

- 한 달 조회 실패 → 그 달만 건너뜀(`fetch_daechi_slots` 내부).
- 대치유수지 전체 조회 실패 → `failures`에 누적 + **직전 박제 결과 유지**, 강남·esongpa는 정상 진행.
- 실패는 매일 아침 요약에 한 줄 보고(기존 구조 재사용).

## 9. 테스트 (TDD)

- `parse_daechi`(완료): 빈자리만 추출·코트(A/B/C)·시각(0~6→07~19, 특히 19시)·찬 행 0건.
- `fetch_daechi_slots`: 받기off→빈, 시간필터, 미래필터, 네트워크 예외 안 던짐(시설 격리).
  네트워크는 `requests.Session.get` monkeypatch + `_months` 1달 고정.
- `is_daechi_due`(순수함수):
  - 새벽(예: 03시) → False / 08시 last=None → True
  - 08시 last=10분 전 → False(미경과) / 08시 last=20분 전 → True(경과)
  - 23시 → True(시간창 안) / 00시(자정) → False(시간창 밖)
- `save/load_daechi_fetch_time`: tmp_path 왕복 저장·로드, 없는 파일 → None.

## 10. 범위·안전

- **읽기 전용**, 기존 부품(강남·esongpa·필터·알림) **무수정**. `state.py`에는 함수만 추가.
- **공지 존중**: 15분 간격 + 08~24시 시간창으로 접속을 하루 ~64회로 제한.
- 세익 재고 앱과 **완전히 무관**한 개인용 봇(별도 폴더·독립 git).
- **배포는 별도**: GitHub push 전 사용자 승인(push해야 실제 가동).

### 후속(이번 범위 밖, 선택)
- 알림 끝의 예약 링크(`RESERVE_URL`)는 현재 강남 1개 공용. 시설별 링크는 추후(지금은 동일).
- 빈도/시간창을 settings.yaml로 빼는 것은 YAGNI(지금은 코드 상수로 충분).
