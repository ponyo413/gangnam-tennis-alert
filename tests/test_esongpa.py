# tests/test_esongpa.py
"""esongpa(송파·잠실) 파싱 — 고정 HTML로 동작 박제."""
from src.esongpa import parse_esongpa, _is_intake_closed

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


# ── 접수시간 "닫힘" 자동 감지 ──────────────────────────────
# 잠실은 낮 접수시간에만 예약가능(status_y)이 뜨고, 저녁엔 빈칸도 전부
# 접수불가(status_e)로 잠긴다(2026-06-23 디버그 실측). 그래서 "예약가능 0 +
# 접수불가만 잔뜩"이면 '지금은 접수시간 아님'으로 보고, 그 시각 결과를 무시해야 한다.

def _status_cells(pairs):
    """(시작시각, status클래스) 목록을 esongpa 시간칸 HTML로 만든다(닫힘 판정 테스트용)."""
    return "".join(
        f"<li>{t}~00:00<span class='{cls}'>표시</span></li>" for t, cls in pairs
    )


def test_intake_open_when_available_slots_exist():
    """낮(접수시간): 예약가능(status_y) 칸이 하나라도 있으면 '열림' — 닫힘 아님."""
    # 어제 낮 12:59 실측 축약 — 예약가능 다수 + 지나간 칸(접수불가) 소수
    html = _status_cells([
        ("06:00", "status_y"), ("08:00", "status_y"), ("10:00", "status_y"),
        ("08:00", "status_e"),  # 이미 지나간 시각 1개
    ])
    assert _is_intake_closed(html) is False


def test_intake_closed_when_only_unavailable():
    """저녁(마감): 예약가능 0 + 접수불가(status_e)만 잔뜩 → '닫힘'."""
    # 어제 저녁 21:18 실측 축약 — 모든 빈칸이 접수불가시간으로 잠김
    html = _status_cells([
        ("06:00", "status_e"), ("08:00", "status_e"),
        ("16:00", "status_e"), ("18:00", "status_e"),
    ])
    assert _is_intake_closed(html) is True


def test_intake_not_closed_when_fully_booked():
    """진짜 다 참: 예약완료(status_g)만이라 빈칸 자체가 없음 → 닫힘 아님(빈자리 0이 사실)."""
    html = _status_cells([("06:00", "status_g"), ("08:00", "status_g")])
    assert _is_intake_closed(html) is False


def test_closed_site_keeps_previous_slots(monkeypatch):
    """접수 닫힘(저녁)이면 그 시설은 직전 슬롯을 그대로 유지한다 — 가짜 변동 알림 방지.

    저녁엔 잠실 빈칸이 전부 접수불가라 새로 뽑히는 빈자리가 0건이 된다. 그대로 0으로
    기록하면 다음 낮에 빈자리가 다시 나타날 때 '현황 바뀜!' 가짜 알림이 터진다.
    그래서 닫힘일 땐 '낮에 마지막으로 본' 직전 빈자리를 유지해야 한다.
    """
    import src.esongpa as e
    from src.models import Slot
    monkeypatch.setenv("SONGPA_ID", "x")
    monkeypatch.setenv("SONGPA_PW", "y")
    monkeypatch.setattr(e, "_login", lambda session, base: True)
    # 잠실 한 곳만 조회하도록 시설 목록을 줄인다
    monkeypatch.setattr(e, "ESONGPA_SITES",
                        [{"center": "잠실", "base": "http://x", "list_page": "s07.od.list.php"}])
    # 모든 조회가 '저녁(접수불가만)' HTML을 반환 → 닫힘으로 판정돼야 함
    closed_html = "<li>18:00~20:00<span class='status_e'>접수불가시간</span></li>"

    class FakeResp:
        text = closed_html

    monkeypatch.setattr("requests.Session.get", lambda self, *a, **k: FakeResp())

    previous = [Slot("잠실", "테니스장", "2099-01-03", "18:00")]
    settings = {"잠실": {"받기": True, "토": [18, 20], "일": [18, 20],
                         "월": [20], "화": [20], "수": [20]}}
    result = e.fetch_esongpa_slots(settings, previous)
    assert previous[0] in result  # 직전에 보던 잠실 빈자리가 유지됨
