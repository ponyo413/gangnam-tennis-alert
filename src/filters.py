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
