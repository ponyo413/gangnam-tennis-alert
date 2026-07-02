# src/settings_loader.py
"""설정표(settings.yaml) 읽기 + 검증 + 폴백.

사용자가 settings.yaml을 고쳐도 형식이 틀리면 봇이 멈추지 않게,
직전 정상 설정 백업(settings.last_good.yaml) 또는 코드 내장 기본값으로 폴백한다.
"""
from pathlib import Path

import yaml

# 코드 내장 기본값(설정표가 없거나 첫 실행 시) — 현재 운영(settings.yaml)과 일치시킴.
# settings.yaml 시간대를 바꾸면 이 기본값도 함께 갱신해야 폴백(비상시) 때 동일하게 작동한다.
DEFAULT_SETTINGS = {
    "강남": {"받기": True, "매일": [19, 20, 21]},
    "송파": {"받기": True, "토": [8, 10]},
    "잠실": {"받기": True, "토": [8, 10, 18, 20], "일": [18, 20],
             "월": [20], "화": [20], "수": [20]},
    "대치유수지": {"받기": True, "평일": [19], "토": [7, 9, 19]},
    "올림픽공원레슨": {"받기": True, "코트": ["실외", "실내"], "주중": [19]},
}

# date.weekday() 0~6 → 요일 글자. 설정표 키와 필터(filters)가 공유하는 단일 출처.
WEEKDAY_KEYS = ["월", "화", "수", "목", "금", "토", "일"]


# 시간 설정에 쓸 수 있는 키: 요일(월~일) + 매일 + 평일/주말 묶음
TIME_KEYS = set(WEEKDAY_KEYS) | {"매일", "평일", "주말"}

# 올림픽공원레슨 블록 전용 허용값(빈자리 시설과 형식이 달라 따로 검증)
# - 코트: 실외(야외 코트) 또는 실내(실내 코트) 글자 목록
# - 요일 키: 주중(월~금), 주말(토·일), 수요일(특정 요일)
_OLYMPIC_COURTS = {"실외", "실내"}
_OLYMPIC_DAY_KEYS = {"주중", "주말", "수요일"}


def _validate_olympic_block(cfg):
    """올림픽공원레슨 블록 검증 — 받기(bool) + 코트(실외/실내 목록) + 요일(주중/주말/수요일→시각목록).

    빈자리 시설(강남/송파/잠실/대치유수지)과 형식이 다르기 때문에 별도 검증 함수로 분리.
    - 코트: 실외/실내 중 하나 이상의 글자 목록
    - 요일 키: 주중/주말/수요일 중 하나 → 정수 목록(시각)
    """
    if not isinstance(cfg.get("받기"), bool):
        raise ValueError("'올림픽공원레슨'의 '받기'는 true 또는 false여야 합니다")
    courts = cfg.get("코트", [])
    if not (isinstance(courts, list) and all(c in _OLYMPIC_COURTS for c in courts)):
        raise ValueError("'올림픽공원레슨'의 '코트'는 실외/실내 목록이어야 합니다")
    if not courts:
        raise ValueError("'올림픽공원레슨'의 '코트'는 최소 하나(실외/실내) 골라야 합니다")
    for key, val in cfg.items():
        if key in ("받기", "코트"):
            continue
        if key not in _OLYMPIC_DAY_KEYS:
            raise ValueError(f"'올림픽공원레슨'의 '{key}'는 주중/주말/수요일이어야 합니다")
        if not (isinstance(val, list) and all(isinstance(h, int) for h in val)):
            raise ValueError(f"'올림픽공원레슨 {key}'의 시간은 숫자 목록이어야 합니다(예: [19])")


def _validate_time_block(label, cfg):
    """시간 설정 한 덩어리(요일/매일/평일/주말 → 숫자 목록)를 검증한다."""
    for key, val in cfg.items():
        if key not in TIME_KEYS:
            raise ValueError(f"'{label}'의 '{key}'는 요일(월~일)·매일·평일·주말이어야 합니다")
        if not (isinstance(val, list) and all(isinstance(h, int) for h in val)):
            raise ValueError(f"'{label} {key}'의 시간은 숫자 목록이어야 합니다(예: [19, 20])")


def validate_settings(data):
    """설정 dict가 올바른 형식인지 검사. 틀리면 ValueError를 던진다."""
    if not isinstance(data, dict):
        raise ValueError("설정표 최상위가 시설 목록(표)이 아닙니다")
    for fac, cfg in data.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"'{fac}' 설정이 표 형식이 아닙니다")
        # 올림픽공원레슨은 형식이 달라(코트=글자목록, 요일=주중/주말/수요일)
        # 빈자리 시설용 time-key 검증을 건너뛰고 전용 함수로 검증한다.
        if fac == "올림픽공원레슨":
            _validate_olympic_block(cfg)
            continue
        if not isinstance(cfg.get("받기"), bool):
            raise ValueError(f"'{fac}'의 '받기'는 true 또는 false여야 합니다")
        for key, val in cfg.items():
            if key == "받기":
                continue
            if key == "코트추가":
                # 코트추가: {"포이 코트A": {시간설정}, ...} 형태의 표
                if not isinstance(val, dict):
                    raise ValueError(f"'{fac}'의 '코트추가'는 코트별 표여야 합니다")
                for court, court_cfg in val.items():
                    if not isinstance(court_cfg, dict):
                        raise ValueError(f"'{fac} 코트추가 {court}'는 표 형식이어야 합니다")
                    _validate_time_block(f"{fac} 코트추가 {court}", court_cfg)
                continue
            # 그 외는 시간 키(요일/매일/평일/주말)여야 함
            if key not in TIME_KEYS:
                raise ValueError(f"'{fac}'의 '{key}'는 요일(월~일)·매일·평일·주말·코트추가여야 합니다")
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
