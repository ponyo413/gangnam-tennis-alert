"""대치유수지 파싱·조회 동작 박제 — 고정 HTML + 네트워크 monkeypatch."""
from src.daechi import parse_daechi, fetch_daechi_slots

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


# ──────────────────────────────────────────────
# Task 2: fetch_daechi_slots 조회+필터 테스트
# ──────────────────────────────────────────────
def test_fetch_skips_when_disabled():
    """받기=False거나 설정이 없으면 조회 자체를 안 하고 빈 목록."""
    assert fetch_daechi_slots({"대치유수지": {"받기": False}}) == []
    assert fetch_daechi_slots({}) == []


def test_fetch_filters_time_and_drops_past(monkeypatch):
    """원하는 시각(매일 [7])만 + 미래만 남긴다. 과거·다른시각은 제외."""
    html = (
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        "<dl><dd>07:00~09:00</dd>"
        "<dt><a data-date=\"2000-01-01\" data-time=\"0\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
        "<dl><dd>09:00~11:00</dd>"
        "<dt><a data-date=\"2099-07-04\" data-time=\"1\"><img src=\"possible_icn_on.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt>"
        "<dt><a><img src=\"possible_icn_off.gif\"></a></dt></dl>"
    )

    class FakeResp:
        text = html

    monkeypatch.setattr("requests.Session.get", lambda self, *a, **k: FakeResp())
    monkeypatch.setattr("src.daechi._months", lambda today: [(2099, 7)])

    settings = {"대치유수지": {"받기": True, "매일": [7]}}
    slots = fetch_daechi_slots(settings)

    assert len(slots) == 1
    assert slots[0].date == "2099-07-04"
    assert slots[0].time == "07:00"
    assert slots[0].place == "A코트"


def test_fetch_does_not_raise_on_network_error(monkeypatch):
    """조회가 터져도 예외를 밖으로 던지지 않고 빈 목록(다른 시설 알림 보호)."""
    def boom(self, *a, **k):
        raise RuntimeError("연결 실패")

    monkeypatch.setattr("requests.Session.get", boom)
    settings = {"대치유수지": {"받기": True, "매일": [7]}}
    assert fetch_daechi_slots(settings) == []
