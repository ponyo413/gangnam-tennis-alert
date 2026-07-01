"""올림픽공원 레슨 대기 감시 부품 테스트 — 순수 로직 + 고정 HTML + 네트워크 monkeypatch."""
from src.olympic import classify_change


def test_마감에서_숫자면_열림():
    assert classify_change("마감", "19") == "열림"


def test_숫자에서_다른숫자면_변동():
    assert classify_change("19", "17") == "변동"


def test_숫자에서_마감이면_닫힘():
    assert classify_change("17", "마감") == "닫힘"


def test_숫자에서_X면_닫힘():
    assert classify_change("19", "X") == "닫힘"


def test_같은_값이면_None():
    assert classify_change("19", "19") is None
    assert classify_change("마감", "마감") is None


def test_마감과_X_사이는_조용():
    """둘 다 대기 불가·숫자 없음 → 알림 없음."""
    assert classify_change("마감", "X") is None
    assert classify_change("X", "마감") is None


def test_처음_등장한_숫자는_열림():
    """직전 기록이 없던 칸(None)에 숫자가 뜨면 '열림'(첫 실행은 main이 별도 차단)."""
    assert classify_change(None, "19") == "열림"


def test_처음_등장한_마감은_조용():
    assert classify_change(None, "마감") is None
