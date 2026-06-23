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
