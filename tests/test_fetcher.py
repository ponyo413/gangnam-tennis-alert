"""조회기 파서 테스트: use_yn=='N'(빈자리) + 미래 시간만 골라야 함.
(실제 사이트 호출 부분은 수동 검증; 여기선 응답 해석 로직만 검증)"""
from datetime import datetime, timezone, timedelta

from src.models import Slot
from src.fetcher import parse_slots, month_base_dates

KST = timezone(timedelta(hours=9))


def test_빈자리_N만_그리고_미래만_파싱():
    now = datetime(2026, 6, 22, 12, 0, tzinfo=KST)  # 6/22(월) 정오 기준
    raw = [
        {"date": "20260625", "start_time": "19:00", "use_yn": "N"},  # 미래·N → 포함
        {"date": "20260625", "start_time": "20:00", "use_yn": "Y"},  # 예약완료 → 제외
        {"date": "20260622", "start_time": "06:00", "use_yn": "N"},  # 오늘이지만 지난 시간 → 제외
        {"date": "20260622", "start_time": "15:00", "use_yn": "N"},  # 오늘 오후(정오 후) → 포함
        {"date": "20260626", "start_time": "10:00", "use_yn": "E"},  # 마감 → 제외
    ]
    slots = parse_slots(raw, "포이", "코트A", now)

    assert Slot("포이", "코트A", "2026-06-25", "19:00") in slots
    assert Slot("포이", "코트A", "2026-06-22", "15:00") in slots
    assert len(slots) == 2  # 나머지(Y·지난시간·E)는 모두 제외


def test_빈_응답은_빈_목록():
    now = datetime(2026, 6, 22, 12, 0, tzinfo=KST)
    assert parse_slots([], "포이", "코트A", now) == []


def test_다음달_기준날짜_2개():
    dates = month_base_dates(datetime(2026, 6, 22, tzinfo=KST).date())
    assert dates[0] == "20260622"
    assert dates[1] == "20260701"  # 다음달 1일


def test_12월은_다음해_1월로_넘어감():
    dates = month_base_dates(datetime(2026, 12, 10, tzinfo=KST).date())
    assert dates[1] == "20270101"
