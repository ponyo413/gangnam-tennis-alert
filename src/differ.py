"""직전 빈자리 목록과 이번 목록을 비교해 '새로 생긴 빈자리'만 찾는다."""
from src.models import Slot


def find_new_slots(current: list[Slot], previous: list[Slot]) -> list[Slot]:
    """이번(current)에는 있는데 직전(previous)에는 없던 빈자리만 돌려준다.

    Slot이 frozen=True라 set으로 빠르게 '있었나?' 확인 가능.
    current의 순서는 그대로 유지한다.
    """
    previous_set = set(previous)
    return [slot for slot in current if slot not in previous_set]


def has_changed(current: list[Slot], previous: list[Slot]) -> bool:
    """빈자리 목록이 직전과 달라졌는지(추가·삭제 무관, 순서 무시).

    빈자리 현황이 바뀔 때마다 '현재 전체 현황'을 알리기 위해 쓴다.
    """
    return set(current) != set(previous)


def find_opened(current: dict, previous: dict) -> list:
    """신청 상태가 '준비중' → '접수중'으로 바뀐 시설명 목록을 돌려준다.

    직전 기록이 없는 시설은 전환으로 보지 않는다(첫 실행 폭탄 방지).
    """
    opened = []
    for name, info in current.items():
        prev_state = previous.get(name, {}).get("state")
        if prev_state == "준비중" and info.get("state") == "접수중":
            opened.append(name)
    return opened
