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


def test_시설상태_저장_불러오기(tmp_path):
    from src.state import save_status, load_status
    path = tmp_path / "status.json"
    status = {"포이 테니스장": {"state": "준비중", "receipt": "6/24~6/29", "period": "-"}}
    save_status(path, status)
    assert load_status(path) == status


def test_없는_상태파일은_빈_dict(tmp_path):
    from src.state import load_status
    assert load_status(tmp_path / "none.json") == {}


def test_연속실패_카운트_저장_불러오기(tmp_path):
    """강남 조회 연속 실패 횟수를 파일에 저장하고 그대로 다시 읽어야 함."""
    from src.state import save_fail_count, load_fail_count
    path = tmp_path / "read_fail.json"
    save_fail_count(path, 3)
    assert load_fail_count(path) == 3


def test_없는_카운트파일은_0(tmp_path):
    """카운트 파일이 없으면(첫 실행) 0으로 시작."""
    from src.state import load_fail_count
    assert load_fail_count(tmp_path / "none.json") == 0
