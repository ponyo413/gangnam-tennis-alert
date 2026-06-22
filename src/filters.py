"""원하는 시간대(평일 저녁 + 주말) 빈자리만 골라내는 필터."""
from datetime import date
from src.models import Slot
from src.config import WEEKDAY_EVENING_START, WEEKDAY_EVENING_END


def is_wanted_time(slot: Slot) -> bool:
    """이 빈자리가 사용자가 원하는 시간대인지 판단.

    - 주말(토·일): 시간 상관없이 모두 원함 → True
    - 평일(월~금): 저녁(18~21시 시작)만 원함
    """
    y, m, d = (int(x) for x in slot.date.split("-"))
    weekday = date(y, m, d).weekday()  # 월=0 ... 토=5, 일=6

    if weekday >= 5:  # 토(5)·일(6) = 주말
        return True

    # 평일이면 시작 시각(시)만 떼서 저녁 범위인지 확인
    hour = int(slot.time.split(":")[0])
    return WEEKDAY_EVENING_START <= hour < WEEKDAY_EVENING_END
