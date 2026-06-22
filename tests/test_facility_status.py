"""신청상태 파서 테스트: place_detail 응답에서 상태/접수기간/이용기간만 뽑아야 함."""
from src.fetcher import parse_status


def test_상태_필드_추출():
    detail = {
        "state_nm": "접수중",
        "receipt_period": "2026-06-24~2026-06-29",
        "period": "2026-07-01~2026-07-31",
        "confirm_type": "심의승인",
    }
    assert parse_status(detail) == {
        "state": "접수중",
        "receipt": "2026-06-24~2026-06-29",
        "period": "2026-07-01~2026-07-31",
    }


def test_빈_필드는_빈_문자열():
    assert parse_status({}) == {"state": "", "receipt": "", "period": ""}
