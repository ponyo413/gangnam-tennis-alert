"""알림 메시지 만들기 테스트."""
from src.models import Slot
from src.notifier import format_message


def test_빈자리_하나_메시지():
    msg = format_message([Slot("포이", "코트A", "2026-06-25", "19:00")])
    assert "포이" in msg
    assert "코트A" in msg
    assert "2026-06-25" in msg
    assert "19:00" in msg


def test_여러_빈자리_모두_포함():
    slots = [
        Slot("포이", "코트A", "2026-06-25", "19:00"),
        Slot("세곡", "1번코트", "2026-06-27", "10:00"),
    ]
    msg = format_message(slots)
    assert "포이" in msg and "세곡" in msg


def test_빈_목록은_빈_문자열():
    assert format_message([]) == ""


def test_신청시작_메시지():
    from src.notifier import format_application_message
    info = {"state": "접수중", "receipt": "2026-06-24~2026-06-29", "period": "2026-07-01~2026-07-31"}
    msg = format_application_message("포이 테니스장", info)
    assert "포이 테니스장" in msg and "신청 시작" in msg and "2026-06-24~2026-06-29" in msg


from src.notifier import format_summary
from src.models import Slot


def test_summary_lists_slots_sorted():
    slots = [
        Slot("세곡", "3번코트", "2026-07-02", "21:00"),
        Slot("송파", "테니스장", "2026-07-04", "08:00"),
    ]
    msg = format_summary(slots)
    assert "빈자리 현황" in msg
    assert "세곡" in msg and "송파" in msg
    assert "2026-07-02" in msg


def test_summary_empty_says_none():
    msg = format_summary([])
    assert "빈자리 없음" in msg


def test_요약에_실패보고_붙는다():
    msg = format_summary([], failures={"잠실": 3})
    assert "현재 빈자리 없음" in msg
    assert "잠실" in msg and "3" in msg and "실패" in msg


def test_실패없으면_실패줄_없음():
    msg = format_summary([], failures={})
    assert "실패" not in msg


def test_summary_제목_바꿀수있다():
    msg = format_summary([], title="🔔 빈자리 현황이 바뀌었어요")
    assert "🔔 빈자리 현황이 바뀌었어요" in msg
    assert "오늘의 빈자리 현황" not in msg
