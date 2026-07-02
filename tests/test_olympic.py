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


from src.olympic import build_targets, parse_olympic

# 실측 구조 축약: 첫 칸=요일, 둘째 칸=코트, 셋째 칸부터 시간칸. 값=마감/숫자/X.
_SAMPLE = (
    "<table>"
    "<tr><th>요일</th><th>시간/코트</th><th>18시</th><th>19시</th><th>20시</th></tr>"
    "<tr><th>주중</th><th>실외</th><td>마감</td><td>마감</td><td>마감</td></tr>"
    "<tr><th>주중</th><th>실내</th><td>마감</td><td>3</td><td>X</td></tr>"
    "</table>"
)


def test_build_targets_받기off거나_없으면_빈목록():
    assert build_targets({"받기": False, "코트": ["실외"], "주중": [19]}) == []
    assert build_targets(None) == []


def test_build_targets_주중_두_코트():
    got = build_targets({"받기": True, "코트": ["실외", "실내"], "주중": [19]})
    assert set(got) == {("주중", "실외", 19), ("주중", "실내", 19)}


def test_build_targets_잘못된_코트는_무시():
    got = build_targets({"받기": True, "코트": ["실외", "옥상"], "주중": [19]})
    assert got == [("주중", "실외", 19)]


def test_parse_reads_target_cells():
    targets = [("주중", "실외", 19), ("주중", "실내", 19)]
    got = parse_olympic(_SAMPLE, targets)
    assert got == {"주중 실외 19시": "마감", "주중 실내 19시": "3"}


def test_parse_handles_X_and_column_shift():
    """19시 열 위치가 달라져도(헤더 지도로 찾음) 값을 정확히 읽는다."""
    html = (
        "<table>"
        "<tr><th>요일</th><th>시간/코트</th><th>20시</th><th>19시</th></tr>"
        "<tr><th>주중</th><th>실내</th><td>마감</td><td>X</td></tr>"
        "</table>"
    )
    assert parse_olympic(html, [("주중", "실내", 19)]) == {"주중 실내 19시": "X"}


def test_parse_skips_targets_not_in_table():
    """표에 없는 대상(주말)은 결과에 없다(예외 없이 건너뜀)."""
    assert parse_olympic(_SAMPLE, [("주말", "실외", 19)]) == {}


from src.olympic import build_olympic_messages, fetch_olympic_states


def test_build_messages_바뀐_칸만_문구():
    """실외는 마감→3(열림), 실내는 그대로 → 문구 1개(실외 열림)."""
    prev = {"주중 실외 19시": "마감", "주중 실내 19시": "19"}
    cur = {"주중 실외 19시": "3", "주중 실내 19시": "19"}
    msgs = build_olympic_messages(cur, prev)
    assert len(msgs) == 1
    assert "주중 실외 19시" in msgs[0] and "대기 열림" in msgs[0]


def test_build_messages_변동은_화살표():
    prev = {"주중 실내 19시": "19"}
    cur = {"주중 실내 19시": "15"}
    msgs = build_olympic_messages(cur, prev)
    assert len(msgs) == 1
    assert "19" in msgs[0] and "15" in msgs[0]


def test_fetch_받기off는_빈dict():
    assert fetch_olympic_states({"올림픽공원레슨": {"받기": False}}) == {}
    assert fetch_olympic_states({}) == {}


def test_fetch_네트워크오류면_None(monkeypatch):
    """조회가 터지면 예외를 밖으로 던지지 않고 None(main이 직전 유지)."""
    def boom(self, *a, **k):
        raise RuntimeError("연결 실패")
    monkeypatch.setattr("requests.Session.get", boom)
    settings = {"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": [19]}}
    assert fetch_olympic_states(settings) is None


def test_fetch_정상파싱(monkeypatch):
    html = (
        "<table>"
        "<tr><th>요일</th><th>시간/코트</th><th>19시</th></tr>"
        "<tr><th>주중</th><th>실외</th><td>마감</td></tr>"
        "</table>"
    )

    class FakeResp:
        text = html
        encoding = "utf-8"

    monkeypatch.setattr("requests.Session.get", lambda self, *a, **k: FakeResp())
    settings = {"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": [19]}}
    assert fetch_olympic_states(settings) == {"주중 실외 19시": "마감"}
