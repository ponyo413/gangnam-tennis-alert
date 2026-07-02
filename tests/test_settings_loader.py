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


# ── [검토 보강] 비상 기본값(DEFAULT_SETTINGS)을 현재 운영 설정과 일치시킨다.
#    설정표(settings.yaml)가 깨지고 직전 정상 백업(last_good)마저 없을 때 이 값으로 도는데,
#    예전엔 대치유수지가 통째로 빠지고 잠실 토요일 오전(8·10시)도 없어 그 알림이 끊겼다.
def test_기본값에_운영_시설이_모두_있다():
    """비상 기본값에도 운영 중인 시설이 다 들어 있어야 한다(폴백 시 알림 끊김 방지)."""
    assert set(DEFAULT_SETTINGS) == {"강남", "송파", "잠실", "대치유수지", "올림픽공원레슨"}


def test_기본값_잠실_토요일에_오전도_포함():
    """비상 기본값 잠실 토요일 = 오전 8·10시 + 저녁 18·20시(운영 설정과 일치)."""
    assert DEFAULT_SETTINGS["잠실"]["토"] == [8, 10, 18, 20]


def test_기본값_대치유수지_시간대():
    """비상 기본값 대치유수지 = 평일 19시 + 토 7·9·19시(운영 설정과 일치)."""
    assert DEFAULT_SETTINGS["대치유수지"]["평일"] == [19]
    assert DEFAULT_SETTINGS["대치유수지"]["토"] == [7, 9, 19]


def test_기본값_자체가_형식검증_통과():
    """비상 기본값이 validate_settings를 통과해야 한다(폴백이 또 깨지지 않게)."""
    assert validate_settings(DEFAULT_SETTINGS) == DEFAULT_SETTINGS


def test_올림픽_코트_비면_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": [], "주중": [19]}})


# ── 올림픽공원레슨 블록(빈자리 시설과 모양이 다름: 코트=글자목록, 요일=주중/주말/수요일) ──
def test_올림픽_블록_유효():
    data = {"올림픽공원레슨": {"받기": True, "코트": ["실외", "실내"], "주중": [19]}}
    assert validate_settings(data) == data


def test_올림픽_코트값_틀리면_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["옥상"], "주중": [19]}})


def test_올림픽_이상한_요일키_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["실외"], "월화": [19]}})


def test_올림픽_시간이_숫자목록_아니면_오류():
    with pytest.raises(ValueError):
        validate_settings({"올림픽공원레슨": {"받기": True, "코트": ["실외"], "주중": "저녁"}})


def test_기본값_올림픽공원레슨_시간대():
    assert DEFAULT_SETTINGS["올림픽공원레슨"] == {"받기": True, "코트": ["실외", "실내"], "주중": [19]}
