"""원하는 시간대 빈자리만 골라내는 필터 (설정표 기반).

기존의 시설별 하드코딩 함수(강남/송파/잠실 각각) 대신, 시설 설정 dict를 받는
범용 함수 하나로 통일한다. 설정은 settings.yaml → settings_loader 가 읽어 넘긴다.
"""
from datetime import date

from src.models import Slot
from src.settings_loader import WEEKDAY_KEYS

# 묶음 키 — '평일'은 월~금, '주말'은 토·일을 한 줄로 적게 해준다
_WEEKDAYS = ("월", "화", "수", "목", "금")
_WEEKEND = ("토", "일")


def _hours_for(cfg: dict, day_key: str) -> list:
    """설정(cfg)에서 그 요일의 시간 목록을 꺼낸다.

    우선순위: 요일(월~일) > 평일/주말 묶음 > 매일.
    예: {"평일": [7], "매일": [19]} → 월요일 [7], 일요일 [19](평일 아님 → 매일).
    """
    if day_key in cfg:
        return cfg[day_key]
    if day_key in _WEEKDAYS and "평일" in cfg:
        return cfg["평일"]
    if day_key in _WEEKEND and "주말" in cfg:
        return cfg["주말"]
    return cfg.get("매일", [])


def is_wanted_for(slot: Slot, fac_cfg: dict) -> bool:
    """이 빈자리가 알림 대상인지 판단 — 시설 공통 시간대 + 코트별 추가 시간대.

    fac_cfg 예시:
      {"받기": True, "매일": [19, 20, 21]}                              # 모든 코트 공통
      {"받기": True, "매일": [19,20,21], "코트추가": {"포이 코트A": {"평일": [7]}}}
    규칙:
      - 받기=False면 무조건 제외(그 시설 알림 끔)
      - 빈자리 시각이 ① 시설 공통 시간대 또는 ② 그 코트의 추가 시간대에 있으면 대상
      - '코트추가'에 없는 코트는 ①만(지금과 동일). 코트 키 = "{court} {place}"
    """
    if not fac_cfg.get("받기"):
        return False
    y, m, d = (int(x) for x in slot.date.split("-"))
    day_key = WEEKDAY_KEYS[date(y, m, d).weekday()]   # 월=0 … 일=6
    hour = int(slot.time.split(":")[0])
    # ① 시설 공통 시간대
    if hour in _hours_for(fac_cfg, day_key):
        return True
    # ② 그 코트만의 추가 시간대(설정돼 있으면)
    court_cfg = fac_cfg.get("코트추가", {}).get(f"{slot.court} {slot.place}")
    if court_cfg and hour in _hours_for(court_cfg, day_key):
        return True
    return False
