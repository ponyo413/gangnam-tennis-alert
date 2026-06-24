"""대치유수지 파싱·조회 동작 박제 — 고정 HTML + 네트워크 monkeypatch."""
from src.daechi import parse_daechi

# 실측 구조 축약: 한 <dl>=한 시간대 행, <dt> 3개=A·B·C 코트.
# '가능'(possible_icn_on) 칸만 data-date/data-time을 가진다.
SAMPLE_HTML = (
    "<dl><dd>07:00~09:00</dd>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\" data-date=\"2099-07-04\" data-time=\"0\" data-type=\"9\">"
    "<img src=\"/images/sub/possible_icn_on.gif\" title=\"가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "</dl>"
    "<dl><dd>19:00~21:00</dd>"
    "<dt><a href=\"#\" class=\"_rev\" data-date=\"2099-07-04\" data-time=\"6\" data-type=\"9\">"
    "<img src=\"/images/sub/possible_icn_on.gif\" title=\"가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "<dt><a href=\"#\" class=\"_rev\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
    "</dl>"
)


def test_parse_extracts_only_available_with_court_and_time():
    """가능 칸만 추출 + 코트(순서)·시각(7+N*2) 매핑."""
    slots = parse_daechi(SAMPLE_HTML)
    # 07시 행: 2번째 칸(B코트) 가능 / 19시 행: 1번째 칸(A코트) 가능 → 2건
    assert len(slots) == 2
    by_time = {s.time: s for s in slots}

    s07 = by_time["07:00"]
    assert s07.court == "대치유수지"   # 시설명
    assert s07.place == "B코트"        # <dt> 2번째 = B
    assert s07.date == "2099-07-04"

    s19 = by_time["19:00"]
    assert s19.place == "A코트"        # <dt> 1번째 = A
    assert s19.date == "2099-07-04"


def test_parse_ignores_full_rows():
    """모든 칸이 '불가능'인 행은 0건."""
    full = (
        "<dl><dd>13:00~15:00</dd>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "<dt><a href=\"#\"><img src=\"/images/sub/possible_icn_off.gif\" title=\"불가능\" /></a></dt>"
        "</dl>"
    )
    assert parse_daechi(full) == []
