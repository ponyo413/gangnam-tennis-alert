"""시간대 필터 테스트: 평일·주말 구분 없이 저녁 19~21시 시작만 통과해야 함.
(2026-06-24=수, 06-27=토 기준)"""
from src.models import Slot
from src.filters import is_wanted_time


def test_저녁_19_20_21시_통과_평일과주말_모두():
    # 평일(수)
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-24", "19:00")) is True
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-24", "21:00")) is True
    # 주말(토)
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-27", "19:00")) is True
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-27", "20:00")) is True


def test_18시는_제외_평일과주말_모두():
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-24", "18:00")) is False  # 수
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-27", "18:00")) is False  # 토


def test_낮시간_제외_주말도():
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-24", "10:00")) is False  # 평일 낮
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-27", "10:00")) is False  # 주말 낮도 제외


def test_22시_시작은_제외():
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-27", "22:00")) is False


def test_송파_토요일_08_10시만():
    from src.filters import is_songpa_wanted
    # 2026-07-04는 토요일
    assert is_songpa_wanted(Slot("송파", "테니스장", "2026-07-04", "08:00")) is True
    assert is_songpa_wanted(Slot("송파", "테니스장", "2026-07-04", "10:00")) is True
    # 같은 토요일이라도 다른 시간은 제외
    assert is_songpa_wanted(Slot("송파", "테니스장", "2026-07-04", "12:00")) is False
    # 토요일이 아니면 제외 (2026-07-01=수)
    assert is_songpa_wanted(Slot("송파", "테니스장", "2026-07-01", "08:00")) is False
