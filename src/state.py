"""직전 빈자리 목록을 JSON 파일에 저장/불러오기.

GitHub Actions는 실행마다 기억이 초기화되므로, 이 파일을 캐시에 보관해
다음 실행과 비교한다. (상세는 .github/workflows/check.yml 참고)
"""
import json
from pathlib import Path
from src.models import Slot


def save_slots(path, slots: list[Slot]) -> None:
    """빈자리 목록을 JSON 파일로 저장."""
    data = [
        {"court": s.court, "place": s.place, "date": s.date, "time": s.time}
        for s in slots
    ]
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_slots(path) -> list[Slot]:
    """JSON 파일에서 빈자리 목록을 불러옴. 파일이 없으면 빈 목록."""
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Slot(d["court"], d["place"], d["date"], d["time"]) for d in data]


def save_status(path, status: dict) -> None:
    """시설별 신청상태 dict를 JSON으로 저장."""
    Path(path).write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")


def load_status(path) -> dict:
    """시설별 신청상태 dict를 불러옴. 파일이 없으면 빈 dict."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_failures(path) -> dict:
    """시설별 조회 실패 횟수 dict. 파일 없으면 빈 dict."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_failures(path, failures: dict) -> None:
    """시설별 조회 실패 횟수 dict 저장."""
    Path(path).write_text(json.dumps(failures, ensure_ascii=False), encoding="utf-8")


def load_fail_count(path) -> int:
    """강남 조회 '연속 실패' 횟수를 불러옴. 파일이 없거나 깨졌으면 0(첫 실행 취급)."""
    p = Path(path)
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get("count", 0))
    except Exception:
        return 0


def save_fail_count(path, count: int) -> None:
    """강남 조회 '연속 실패' 횟수를 저장."""
    Path(path).write_text(json.dumps({"count": count}, ensure_ascii=False), encoding="utf-8")


def load_daechi_fetch_time(path):
    """대치유수지 마지막 조회 시각(ISO 문자열). 파일이 없거나 깨졌으면 None(아직 조회 안 함)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("at")
    except Exception:
        return None


def save_daechi_fetch_time(path, iso_str) -> None:
    """대치유수지 마지막 조회 시각(ISO 문자열)을 저장."""
    Path(path).write_text(json.dumps({"at": iso_str}, ensure_ascii=False), encoding="utf-8")


def load_summary_date(path):
    """마지막으로 '일일 요약'을 보낸 날짜(YYYY-MM-DD). 파일이 없거나 깨졌으면 None(아직 안 보냄)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("date")
    except Exception:
        return None


def save_summary_date(path, date_str) -> None:
    """'일일 요약'을 보낸 날짜(YYYY-MM-DD)를 저장 — 하루 한 번만 보내려고 기억."""
    Path(path).write_text(json.dumps({"date": date_str}, ensure_ascii=False), encoding="utf-8")
