# 조회기(fetcher) 분석 결과 — A안 확정

> 2026-06-22 강남구 예약 사이트(life.gangnam.go.kr) 실측 분석.
> 결론: **A안(REST API 직접 호출) 확정.** 로그인 불필요, JSON 응답. B안(브라우저 자동화) 불필요.

## 호출 기본

- **ROOT:** `https://life.gangnam.go.kr/`
- **헤더(권장):**
  - `User-Agent`: 일반 브라우저 문자열
  - `X-Requested-With: XMLHttpRequest`
  - `Referer: https://life.gangnam.go.kr/fmcs/54`
- 응답 인코딩 UTF-8 (파이썬 `requests`의 `r.json()`은 정상. 터미널 출력만 깨질 수 있어 `sys.stdout.reconfigure(encoding="utf-8")` 사용)

## 대상 코트 코드 (실측 확정)

| 센터 | company_code | part_code | place_code → 이름 |
|------|-----|-----|-----|
| 포이 테니스장 | `GNCC06` | `04`(일일입장) | `15`=코트A, `16`=코트B |
| 강남세곡체육공원 | `GNCC33` | `04`(테니스장 일일입장) | `13`=1번, `14`=2번, `15`=3번, `16`=4번 코트 |

> ⚠️ 세곡의 `part_code=03`은 **축구장**이므로 제외. 테니스는 `part_code=04`만.
> 참고: 봉은 테니스장은 `GNCC06`이 아니라 `GNCC05` (이번 범위 밖).

## 빈자리 조회 — 효율적 엔드포인트

- **엔드포인트:** `rest/facilities/place_month_time_state_list`
- **방식:** GET
- **파라미터:** `company_code`, `part_code`, `place_code`, `base_date`(YYYYMMDD), `rent_type`(빈 문자열)
- **응답:** 그 달(base_date가 속한 월) 전체의 (날짜 × 시간) 목록. **코트당 1호출.**
- 다음달까지 보려면 `base_date`를 다음달 1일로 바꿔 1회 더 호출.

### 응답 항목 예시
```json
{
  "comcd": "GNCC06", "comnm": "포이 테니스장",
  "date": "20260622", "part_cd": "04", "part_nm": "일일입장",
  "place_cd": "15", "place_nm": null,
  "time_no": "7374", "time_nm": "11회",
  "start_time": "16:00", "end_time": "17:00",
  "use_yn": "N", "rent_amt": 9000
}
```
> `place_nm`이 `null`로 올 수 있음 → 위 표의 place_code→이름 매핑을 코드에 직접 보유.

## 빈자리 판정 기준 (JS 로직에서 확인)

`use_yn` 값의 의미:

| 값 | 의미 |
|----|------|
| **`N`** | ✅ **예약 가능 (빈자리)** |
| `Y` | 예약완료 |
| `E` | 마감 |
| `U` | 예약불가 |
| `D` | 추첨접수 |

→ **빈자리 = `use_yn == 'N'` AND `date >= 오늘`** (과거 날짜도 N으로 오므로 반드시 미래만)

## 구현 시 주의

1. **첫 실행 알림 폭탄 방지:** 현재 N(빈자리)이 수십 건일 수 있음. 첫 실행(직전 기록 없음)은 알림 없이 현재 상태만 저장하고, 둘째 실행부터 "새로 생긴 N"만 알린다.
2. **과거 제외:** 오늘 이전 날짜·지난 시간은 거른다.
3. **예의:** 코트 6개 × (이번달+다음달) = 약 12호출/회. 호출 사이 짧은 간격(예: 0.3~0.5초) 권장.
4. **시간대 필터:** 평일은 저녁(18~21시 시작)만, 주말은 전체 — `filters.is_wanted_time`에서 처리.

## 확정된 fetcher 설계

```
COURTS = [
  {center:"포이", comcd:"GNCC06", part:"04", places:{"15":"코트A","16":"코트B"}},
  {center:"세곡", comcd:"GNCC33", part:"04",
   places:{"13":"1번코트","14":"2번코트","15":"3번코트","16":"4번코트"}},
]
fetch_slots():
  for 코트 in COURTS, place in 코트.places, month in [이번달, 다음달]:
     raw = GET place_month_time_state_list(comcd, part, place, base_date=월1일)
     for item in raw:
        if item.use_yn == 'N' and item.date >= 오늘:
           yield Slot(center, place_name, item.date, item.start_time)
```
