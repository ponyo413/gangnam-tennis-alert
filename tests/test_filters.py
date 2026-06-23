"""시간대 필터(설정 기반 is_wanted_for) 테스트.

요일 확정: 2026-07-04=토, 07-05=일, 07-06=월, 07-07=화, 07-01·08=수, 07-02=목, 07-03=금
"""
from src.filters import is_wanted_for
from src.models import Slot

강남 = {"받기": True, "매일": [19, 20, 21]}
송파 = {"받기": True, "토": [8, 10]}
잠실 = {"받기": True, "토": [18, 20], "일": [18, 20], "월": [20], "화": [20], "수": [20]}


def test_강남_매일_저녁만():
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "20:00"), 강남) is True   # 월 저녁
    assert is_wanted_for(Slot("강남", "x", "2026-07-04", "19:00"), 강남) is True   # 토 저녁
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "18:00"), 강남) is False  # 18시 제외
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "10:00"), 강남) is False  # 낮 제외


def test_송파_토요일_오전만():
    assert is_wanted_for(Slot("송파", "x", "2026-07-04", "08:00"), 송파) is True   # 토
    assert is_wanted_for(Slot("송파", "x", "2026-07-04", "10:00"), 송파) is True
    assert is_wanted_for(Slot("송파", "x", "2026-07-04", "12:00"), 송파) is False  # 다른 시간
    assert is_wanted_for(Slot("송파", "x", "2026-07-01", "08:00"), 송파) is False  # 수(토 아님)


def test_잠실_주말18_20_평일월화수20():
    assert is_wanted_for(Slot("잠실", "x", "2026-07-04", "18:00"), 잠실) is True   # 토 18
    assert is_wanted_for(Slot("잠실", "x", "2026-07-04", "20:00"), 잠실) is True   # 토 20
    assert is_wanted_for(Slot("잠실", "x", "2026-07-05", "18:00"), 잠실) is True   # 일 18
    assert is_wanted_for(Slot("잠실", "x", "2026-07-06", "20:00"), 잠실) is True   # 월 20
    assert is_wanted_for(Slot("잠실", "x", "2026-07-06", "18:00"), 잠실) is False  # 월 18 제외
    assert is_wanted_for(Slot("잠실", "x", "2026-07-02", "20:00"), 잠실) is False  # 목 제외


def test_받기_false면_무조건_제외():
    꺼짐 = {"받기": False, "매일": [19, 20, 21]}
    assert is_wanted_for(Slot("강남", "x", "2026-07-06", "20:00"), 꺼짐) is False
