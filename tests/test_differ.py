"""비교기 테스트: 이번 목록 중 직전에 없던 '새 빈자리'만 돌려줘야 함."""
from src.models import Slot
from src.differ import find_new_slots


def test_새로_생긴_빈자리만_반환():
    previous = [Slot("포이", "코트A", "2026-06-25", "19:00")]
    current = [
        Slot("포이", "코트A", "2026-06-25", "19:00"),   # 직전에도 있던 것 → 제외
        Slot("세곡", "1번코트", "2026-06-27", "10:00"),  # 새로 생김 → 포함
    ]
    result = find_new_slots(current, previous)
    assert result == [Slot("세곡", "1번코트", "2026-06-27", "10:00")]


def test_변화_없으면_빈_목록():
    same = [Slot("포이", "코트A", "2026-06-25", "19:00")]
    assert find_new_slots(same, same) == []


def test_직전이_비어있으면_전부_새것():
    current = [Slot("포이", "코트A", "2026-06-25", "19:00")]
    assert find_new_slots(current, []) == current
