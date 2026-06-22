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
