"""빈자리 한 칸을 나타내는 데이터 구조."""
from dataclasses import dataclass


# frozen=True: 한 번 만들면 못 바꿈 → set(집합)에 넣어 '같은 빈자리인지' 비교 가능
@dataclass(frozen=True)
class Slot:
    court: str   # 센터 이름: "포이" 또는 "세곡"
    place: str   # 코트 이름: "코트A", "1번코트" 등
    date: str    # 날짜: "2026-06-25" (YYYY-MM-DD)
    time: str    # 시작 시간: "19:00" (HH:MM)
