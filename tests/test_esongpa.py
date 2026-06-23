# tests/test_esongpa.py
"""esongpa(송파·잠실) 파싱 — 고정 HTML로 동작 박제."""
from src.esongpa import parse_esongpa

SAMPLE_HTML = (
    "<ul>"
    "<li>19:00~20:00<span class='status_y'>"
    "<a href=\"#\" onclick=\"fn_rent_odchk1('A', '2026-07-04')\">예약가능</a></span></li>"
    "<li>20:00~21:00<span class='status_n'>"
    "<a href=\"#\">예약완료</a></span></li>"
    "</ul>"
)


def test_parse_extracts_only_available_slots():
    slots = parse_esongpa(SAMPLE_HTML, "송파")
    assert len(slots) == 1
    s = slots[0]
    assert s.court == "송파"
    assert s.date == "2026-07-04"
    assert s.time == "19:00"


def test_parse_jamsil_same_structure():
    html = (
        "<li>21:00~22:00<span class='status_y'>"
        "<a href=\"#\" onclick=\"fn_rent_odchk1('B', '2026-07-04')\">예약가능</a></span></li>"
    )
    slots = parse_esongpa(html, "잠실")
    assert len(slots) == 1
    assert slots[0].court == "잠실"
    assert slots[0].date == "2026-07-04"
    assert slots[0].time == "21:00"


def test_fetch_does_not_raise_when_a_site_fails(monkeypatch):
    """한 시설 조회가 실패해도 함수 전체가 죽지 않는다(시설별 격리).

    잠실 로그인이 실패해도 송파/강남 알림이 함께 끊기지 않게 하려는 것.
    """
    import src.esongpa as e
    monkeypatch.setenv("SONGPA_ID", "x")
    monkeypatch.setenv("SONGPA_PW", "y")

    def boom(session, base):
        raise RuntimeError("로그인 실패")

    monkeypatch.setattr(e, "_login", boom)
    # 모든 시설이 실패해도 예외를 던지지 않고 빈 목록을 돌려줘야 한다
    from src.settings_loader import DEFAULT_SETTINGS
    assert e.fetch_esongpa_slots(DEFAULT_SETTINGS) == []
