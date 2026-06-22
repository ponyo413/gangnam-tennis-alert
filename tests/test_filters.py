"""시간대 필터 테스트: 평일 저녁(18~21시 시작) + 주말 전체만 통과해야 함.
(2026-06-24=수, 06-27=토, 06-28=일 기준)"""
from src.models import Slot
from src.filters import is_wanted_time


def test_평일_저녁_통과():
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-24", "19:00")) is True


def test_평일_낮_제외():
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-24", "10:00")) is False


def test_평일_저녁_경계_18시통과_22시제외():
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-24", "18:00")) is True
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-24", "22:00")) is False


def test_주말은_시간무관_통과():
    assert is_wanted_time(Slot("포이", "코트A", "2026-06-27", "10:00")) is True
    assert is_wanted_time(Slot("세곡", "1번코트", "2026-06-28", "07:00")) is True
