"""상태 저장/불러오기 테스트: 빈자리 목록을 파일에 저장하고 그대로 다시 읽어야 함."""
from src.models import Slot
from src.state import save_slots, load_slots


def test_저장한_그대로_불러오기(tmp_path):
    path = tmp_path / "state.json"
    slots = [
        Slot("포이", "코트A", "2026-06-25", "19:00"),
        Slot("세곡", "1번코트", "2026-06-27", "10:00"),
    ]
    save_slots(path, slots)
    assert load_slots(path) == slots


def test_없는_파일은_빈_목록(tmp_path):
    assert load_slots(tmp_path / "none.json") == []
