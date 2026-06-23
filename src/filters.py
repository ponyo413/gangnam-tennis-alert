"""원하는 시간대 빈자리만 골라내는 필터 (설정표 기반).

기존의 시설별 하드코딩 함수(강남/송파/잠실 각각) 대신, 시설 설정 dict를 받는
범용 함수 하나로 통일한다. 설정은 settings.yaml → settings_loader 가 읽어 넘긴다.
"""
from datetime import date

from src.models import Slot
from src.settings_loader import WEEKDAY_KEYS


def is_wanted_for(slot: Slot, fac_cfg: dict) -> bool:
    """이 빈자리가 해당 시설 설정(fac_cfg)상 알림 대상인지 판단.

    fac_cfg 예시:
      {"받기": True, "매일": [19, 20, 21]}                      # 매일 같은 시간
      {"받기": True, "토": [18, 20], "월": [20], ...}            # 요일별로 다름
    규칙:
      - 받기=False면 무조건 제외(그 시설 알림 끔)
      - 그 날짜의 요일 시간 목록(없으면 '매일' 목록)에 시작시각이 있으면 대상
    """
    if not fac_cfg.get("받기"):
        return False
    y, m, d = (int(x) for x in slot.date.split("-"))
    day_key = WEEKDAY_KEYS[date(y, m, d).weekday()]   # 월=0 … 일=6
    hours = fac_cfg.get(day_key, fac_cfg.get("매일", []))
    return int(slot.time.split(":")[0]) in hours
