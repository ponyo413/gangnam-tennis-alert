"""원하는 시간대 빈자리만 골라내는 필터 (시설별로 조건이 다름)."""
from datetime import date
from src.models import Slot
from src.config import EVENING_START, EVENING_END


def is_wanted_time(slot: Slot) -> bool:
    """강남(포이·세곡): 평일·주말 구분 없이 저녁 19~21시 시작만."""
    hour = int(slot.time.split(":")[0])
    return EVENING_START <= hour < EVENING_END


def is_songpa_wanted(slot: Slot) -> bool:
    """송파: 토요일 + 08:00·10:00 시작만 (송파는 08~18시 운영, 사용자 지정)."""
    y, m, d = (int(x) for x in slot.date.split("-"))
    if date(y, m, d).weekday() != 5:  # 월=0 ... 토=5
        return False
    return slot.time in ("08:00", "10:00")


def is_jamsil_wanted(slot: Slot) -> bool:
    """잠실(2시간 단위 시설): 주말 18·20시 + 평일 월·화·수 20시만.

    잠실유수지는 강남(1시간 단위)과 달리 2시간 단위(…14·16·18·20시)로 운영한다.
    그래서 강남용 19~21시 기준이 아니라 실제 칸(18·20시)을 콕 집어 지정한다.
      - 토·일(주말): 18:00·20:00 시작 둘 다 알림
      - 월·화·수: 20:00 시작만 알림
      - 목·금: 알림 없음
    """
    y, m, d = (int(x) for x in slot.date.split("-"))
    weekday = date(y, m, d).weekday()       # 월=0 … 금=4, 토=5, 일=6
    if weekday in (5, 6):                    # 주말(토·일): 두 저녁 타임 모두
        return slot.time in ("18:00", "20:00")
    if weekday in (0, 1, 2):                 # 평일 월·화·수: 늦은 타임만
        return slot.time == "20:00"
    return False                             # 목·금은 알림 없음
