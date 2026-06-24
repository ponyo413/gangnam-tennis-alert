# tests/test_settings_loader.py
"""설정표 읽기·검증·폴백 — 사용자가 틀려도 봇이 안 멈추게."""
import pytest

from src.settings_loader import load_settings, validate_settings, DEFAULT_SETTINGS


def test_정상_설정표를_읽는다(tmp_path):
    p = tmp_path / "settings.yaml"
    p.write_text("강남:\n  받기: true\n  매일: [19, 20]\n", encoding="utf-8")
    settings, err = load_settings(str(p), str(tmp_path / "lg.yaml"))
    assert err is None
    assert settings["강남"]["받기"] is True
    assert settings["강남"]["매일"] == [19, 20]


def test_파일_없으면_기본값(tmp_path):
    settings, err = load_settings(str(tmp_path / "none.yaml"), str(tmp_path / "lg.yaml"))
    assert err is None
    assert settings == DEFAULT_SETTINGS


def test_받기가_불린_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": "응", "매일": [19]}})


def test_시간이_숫자목록_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": True, "매일": "저녁"}})


def test_이상한_요일키_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": True, "토토": [19]}})  # 없는 키('평일'·'주말'은 이제 유효)


def test_평일_주말_코트추가_허용():
    """묶음 키(평일/주말)와 코트추가 섹션은 유효한 설정이다(안 던짐)."""
    data = {"강남": {"받기": True, "매일": [19, 20, 21],
                     "평일": [7], "주말": [12],
                     "코트추가": {"포이 코트A": {"평일": [7]},
                                  "세곡 2번코트": {"주말": [12, 13]}}}}
    assert validate_settings(data) == data


def test_코트추가_시간이_숫자목록_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": True,
                                    "코트추가": {"포이 코트A": {"평일": "아침"}}}})


def test_코트추가가_표가_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"강남": {"받기": True, "코트추가": [1, 2, 3]}})


def test_형식틀리면_직전정상으로_폴백(tmp_path):
    good = tmp_path / "lg.yaml"
    good.write_text("강남:\n  받기: true\n  매일: [19]\n", encoding="utf-8")
    bad = tmp_path / "settings.yaml"
    bad.write_text("강남:\n  받기: 이상한값\n", encoding="utf-8")  # 형식 오류(받기가 bool 아님)
    settings, err = load_settings(str(bad), str(good))
    assert err is not None and "형식 오류" in err
    assert settings["강남"]["매일"] == [19]  # 직전 정상 사용


def test_직전정상도_없으면_기본값(tmp_path):
    bad = tmp_path / "settings.yaml"
    bad.write_text("강남:\n  받기: 이상한값\n", encoding="utf-8")
    settings, err = load_settings(str(bad), str(tmp_path / "none.yaml"))
    assert err is not None
    assert settings == DEFAULT_SETTINGS
