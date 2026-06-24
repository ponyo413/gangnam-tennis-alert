"""시간대 필터(설정 기반 is_wanted_for) 테스트.

요일 확정: 2026-07-04=토, 07-05=일, 07-06=월, 07-07=화, 07-01·08=수, 07-02=목, 07-03=금
"""
from src.filters import is_wanted_for, _hours_for
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


# ── 코트별 추가 시간대 (공통 + 코트추가) ──────────────────
강남_코트추가 = {
    "받기": True,
    "매일": [19, 20, 21],
    "코트추가": {
        "포이 코트A": {"평일": [7]},          # 코트A = 공통 저녁 + 평일 아침 7시
        "세곡 2번코트": {"주말": [12, 13]},   # 세곡2번 = 공통 저녁 + 주말 점심
    },
}


def test_hours_for_우선순위():
    """시간 해석 우선순위: 요일(월~일) > 평일/주말 > 매일."""
    cfg = {"평일": [7], "주말": [12], "매일": [19]}
    assert _hours_for(cfg, "월") == [7]    # 평일(월~금)
    assert _hours_for(cfg, "토") == [12]   # 주말(토·일)
    cfg2 = {"월": [8], "평일": [7]}
    assert _hours_for(cfg2, "월") == [8]   # 요일이 평일보다 우선
    assert _hours_for(cfg2, "화") == [7]   # 화는 요일키 없음 → 평일
    assert _hours_for({"매일": [19]}, "일") == [19]  # 매일 폴백
    assert _hours_for({}, "월") == []                # 아무것도 없으면 빈 목록


def test_코트추가_공통과_추가_둘다_본다():
    """예외 코트는 공통 시간대 + 코트추가 시간대 둘 다 알림 대상."""
    # 코트A: 공통 저녁(월 20시) + 평일 아침 7시 둘 다
    assert is_wanted_for(Slot("포이", "코트A", "2026-07-06", "07:00"), 강남_코트추가) is True   # 월 7시(추가)
    assert is_wanted_for(Slot("포이", "코트A", "2026-07-06", "20:00"), 강남_코트추가) is True   # 월 20시(공통)
    # 코트A 토요일 7시: 평일 아님 → 추가 없음, 공통도 7시 아님 → 제외
    assert is_wanted_for(Slot("포이", "코트A", "2026-07-04", "07:00"), 강남_코트추가) is False


def test_코트추가_없는_코트는_공통만():
    """코트추가에 없는 코트(코트B)는 지금과 동일하게 공통만."""
    assert is_wanted_for(Slot("포이", "코트B", "2026-07-06", "20:00"), 강남_코트추가) is True   # 공통 저녁
    assert is_wanted_for(Slot("포이", "코트B", "2026-07-06", "07:00"), 강남_코트추가) is False  # 7시 추가 없음


def test_코트추가_주말_점심():
    """세곡 2번코트 = 주말 점심 추가."""
    assert is_wanted_for(Slot("세곡", "2번코트", "2026-07-04", "12:00"), 강남_코트추가) is True   # 토 12시(주말 추가)
    assert is_wanted_for(Slot("세곡", "2번코트", "2026-07-06", "12:00"), 강남_코트추가) is False  # 월 12시(주말 아님)
