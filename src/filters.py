"""원하는 시간대(매일 저녁 19~21시 시작) 빈자리만 골라내는 필터."""
from src.models import Slot
from src.config import EVENING_START, EVENING_END


def is_wanted_time(slot: Slot) -> bool:
    """이 빈자리가 사용자가 원하는 시간대인지 판단.

    평일·주말 구분 없이 **저녁(19·20·21시 시작)**만 원함.
    예: 19~20, 20~21, 21~22시. (22시 시작·낮 시간·18시 이전은 제외)
    """
    hour = int(slot.time.split(":")[0])
    return EVENING_START <= hour < EVENING_END
