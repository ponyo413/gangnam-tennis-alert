"""조회기 테스트: 빈자리 = use_yn 'N' AND 예약가능 날짜 AND 미래.
(실제 사이트 호출 부분은 수동 검증; 여기선 응답 해석 로직만 검증)"""
from datetime import datetime, timezone, timedelta

from src.models import Slot
from src.fetcher import parse_slots, parse_open_dates, month_base_dates

KST = timezone(timedelta(hours=9))


def test_예약가능_날짜만_추출():
    # state_cd 10/11=예약가능만, 15(추첨)·20(마감/예약불가)·30(휴관)은 제외
    raw = [
        {"date": "2026-07-01", "state_cd": "10"},  # 예약가능 → 포함
        {"date": "2026-07-02", "state_cd": "11"},  # 예약가능(예비) → 포함
        {"date": "2026-07-03", "state_cd": "15"},  # 추첨 → 제외
        {"date": "2026-07-04", "state_cd": "20"},  # 예약불가 → 제외
        {"date": "2026-07-05", "state_cd": "30"},  # 휴관 → 제외
    ]
    assert parse_open_dates(raw) == {"2026-07-01", "2026-07-02"}


def test_빈자리는_N_그리고_예약가능날_그리고_미래만():
    now = datetime(2026, 6, 22, 12, 0, tzinfo=KST)  # 6/22(월) 정오 기준
    open_dates = {"2026-06-22", "2026-06-25"}        # 이 두 날만 '예약가능'
    raw = [
        {"date": "20260625", "start_time": "19:00", "use_yn": "N"},  # 예약가능·미래·N → 포함
        {"date": "20260625", "start_time": "20:00", "use_yn": "Y"},  # 예약완료 → 제외
        {"date": "20260622", "start_time": "06:00", "use_yn": "N"},  # 오늘 지난 시간 → 제외
        {"date": "20260622", "start_time": "15:00", "use_yn": "N"},  # 예약가능·미래·N → 포함
        {"date": "20260626", "start_time": "10:00", "use_yn": "N"},  # 빈칸이지만 '예약불가 날'(open_dates에 없음) → 제외
    ]
    slots = parse_slots(raw, "포이", "코트A", now, open_dates)

    assert Slot("포이", "코트A", "2026-06-25", "19:00") in slots
    assert Slot("포이", "코트A", "2026-06-22", "15:00") in slots
    assert len(slots) == 2  # Y·지난시간·예약불가날 모두 제외


def test_예약불가_날이면_빈칸이어도_제외():
    # 과거 버그 재현 방지: 모든 날이 예약불가(open_dates 비어있음)면 빈칸이 많아도 0건
    now = datetime(2026, 6, 22, 12, 0, tzinfo=KST)
    raw = [
        {"date": "20260627", "start_time": "20:00", "use_yn": "N"},
        {"date": "20260704", "start_time": "20:00", "use_yn": "N"},
    ]
    assert parse_slots(raw, "포이", "코트B", now, open_dates=set()) == []


def test_빈_응답은_빈_목록():
    now = datetime(2026, 6, 22, 12, 0, tzinfo=KST)
    assert parse_slots([], "포이", "코트A", now, open_dates={"2026-06-22"}) == []


def test_다음달_기준날짜_2개():
    dates = month_base_dates(datetime(2026, 6, 22, tzinfo=KST).date())
    assert dates[0] == "20260622"
    assert dates[1] == "20260701"  # 다음달 1일


def test_12월은_다음해_1월로_넘어감():
    dates = month_base_dates(datetime(2026, 12, 10, tzinfo=KST).date())
    assert dates[1] == "20270101"
