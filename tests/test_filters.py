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


from src.filters import is_jamsil_wanted


# 잠실 규칙(2시간 단위 시설): 주말(토·일) 18·20시 둘 다 / 평일 월·화·수 20시만 / 목·금 없음
# (요일 확정: 2026-07-04=토, 07-05=일, 07-06=월, 07-07=화, 07-01·08=수, 07-02=목, 07-03=금)


def test_잠실_주말_18시20시_둘다_허용():
    # 토(07-04)·일(07-05): 18시·20시 두 타임 모두 알림
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "18:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "20:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-05", "18:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-05", "20:00")) is True


def test_잠실_월화수_20시만_허용():
    # 월(07-06)·화(07-07)·수(07-08): 20시 타임만 알림
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-06", "20:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-07", "20:00")) is True
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-08", "20:00")) is True


def test_잠실_월화수_18시는_제외():
    # 평일(월화수)은 20시만 — 18시는 제외
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-06", "18:00")) is False  # 월
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-08", "18:00")) is False  # 수


def test_잠실_목금은_전부_제외():
    # 목(07-02)·금(07-03)은 알림 없음(저녁이라도)
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-02", "20:00")) is False  # 목
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-03", "20:00")) is False  # 금


def test_잠실_낮시간은_제외():
    # 주말·평일 모두 낮(08·14·16시)은 제외 — 저녁 18·20시만 대상
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "08:00")) is False  # 토 오전
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-04", "14:00")) is False  # 토 낮
    assert is_jamsil_wanted(Slot("잠실", "테니스장", "2026-07-06", "16:00")) is False  # 월 낮
