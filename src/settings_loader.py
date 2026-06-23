# src/settings_loader.py
"""설정표(settings.yaml) 읽기 + 검증 + 폴백.

사용자가 settings.yaml을 고쳐도 형식이 틀리면 봇이 멈추지 않게,
직전 정상 설정 백업(settings.last_good.yaml) 또는 코드 내장 기본값으로 폴백한다.
"""
from pathlib import Path

import yaml

# 코드 내장 기본값(설정표가 없거나 첫 실행 시) — 현재 운영 시간대와 동일
DEFAULT_SETTINGS = {
    "강남": {"받기": True, "매일": [19, 20, 21]},
    "송파": {"받기": True, "토": [8, 10]},
    "잠실": {"받기": True, "토": [18, 20], "일": [18, 20],
             "월": [20], "화": [20], "수": [20]},
}

# date.weekday() 0~6 → 요일 글자. 설정표 키와 필터(filters)가 공유하는 단일 출처.
WEEKDAY_KEYS = ["월", "화", "수", "목", "금", "토", "일"]


def validate_settings(data):
    """설정 dict가 올바른 형식인지 검사. 틀리면 ValueError를 던진다."""
    if not isinstance(data, dict):
        raise ValueError("설정표 최상위가 시설 목록(표)이 아닙니다")
    for fac, cfg in data.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"'{fac}' 설정이 표 형식이 아닙니다")
        if not isinstance(cfg.get("받기"), bool):
            raise ValueError(f"'{fac}'의 '받기'는 true 또는 false여야 합니다")
        for key, val in cfg.items():
            if key == "받기":
                continue
            if key not in WEEKDAY_KEYS and key != "매일":
                raise ValueError(f"'{fac}'의 '{key}'는 요일(월~일) 또는 '매일'이어야 합니다")
            if not (isinstance(val, list) and all(isinstance(h, int) for h in val)):
                raise ValueError(f"'{fac} {key}'의 시간은 숫자 목록이어야 합니다(예: [19, 20])")
    return data


def load_settings(path="settings.yaml", last_good="settings.last_good.yaml"):
    """설정표를 읽어 (검증된 dict, 오류메시지 or None) 반환.

    - 파일 없음: 기본값(정상).
    - 정상: 읽은 설정 + 직전정상 백업 갱신.
    - 형식 오류: 직전 정상 설정 → 없으면 기본값. 봇은 멈추지 않는다.
    """
    p = Path(path)
    if not p.exists():
        return DEFAULT_SETTINGS, None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        validate_settings(data)
        # 정상 읽기 성공 → 이 내용을 "마지막 정상"으로 백업
        Path(last_good).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        return data, None
    except Exception as e:
        # 형식 오류 → 직전 정상 설정으로 폴백, 그것도 없으면 기본값
        lg = Path(last_good)
        if lg.exists():
            try:
                good = validate_settings(yaml.safe_load(lg.read_text(encoding="utf-8")))
                return good, f"설정표 형식 오류({e}). 직전 정상 설정으로 작동합니다."
            except Exception:
                pass
        return DEFAULT_SETTINGS, f"설정표 형식 오류({e}). 기본 설정으로 작동합니다."
