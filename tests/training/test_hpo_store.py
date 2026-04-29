import json

import pytest

from src.training.hpo_store import (
    SYMBOL_GROUPS,
    SYMBOL_TO_GROUP,
    get_best_params_for_symbol,
    load_all_champions,
    load_champion,
    save_champion,
    study_name,
    utc_now_iso,
)


def _champion(model: str = "xgboost", group: str = "dollar_majors") -> dict:
    return {
        "model_name": model,
        "symbol_group": group,
        "role": "champion",
        "params": {"max_depth": 3, "n_estimators": 150},
        "score": 0.72,
        "mean_accuracy": 0.73,
        "avg_overfit_gap": 0.03,
        "trial_number": 42,
        "promoted_at": utc_now_iso(),
        "promotion_reason": "first_promotion",
    }


def test_symbol_to_group_covers_all_symbols():
    all_symbols = {s for symbols in SYMBOL_GROUPS.values() for s in symbols}
    assert all_symbols == set(SYMBOL_TO_GROUP.keys())


def test_symbol_to_group_maps_correctly():
    assert SYMBOL_TO_GROUP["EURUSD"] == "dollar_majors"
    assert SYMBOL_TO_GROUP["USDJPY"] == "yen_crosses"
    assert SYMBOL_TO_GROUP["XAUUSD"] == "commodities"


def test_study_name_format():
    assert study_name("xgboost", "dollar_majors") == "hpo_xgboost_dollar_majors"


def test_save_and_load_champion(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    data = _champion()

    save_champion(data)

    loaded = load_champion("xgboost", "dollar_majors")
    assert loaded is not None
    assert loaded["score"] == 0.72
    assert loaded["params"]["max_depth"] == 3


def test_load_champion_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    assert load_champion("xgboost", "nonexistent_group") is None


def test_load_all_champions_returns_list(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    save_champion(_champion("xgboost", "dollar_majors"))
    save_champion(_champion("random_forest", "yen_crosses"))

    champions = load_all_champions()

    assert len(champions) == 2
    model_names = {c["model_name"] for c in champions}
    assert model_names == {"xgboost", "random_forest"}


def test_load_all_champions_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    assert load_all_champions() == []


def test_get_best_params_for_symbol_returns_params(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    save_champion(_champion("xgboost", "dollar_majors"))

    params = get_best_params_for_symbol("xgboost", "EURUSD")

    assert params == {"max_depth": 3, "n_estimators": 150}


def test_get_best_params_for_symbol_returns_none_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    assert get_best_params_for_symbol("xgboost", "UNKNOWN_SYMBOL") is None


def test_get_best_params_for_symbol_returns_none_when_no_champion(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    assert get_best_params_for_symbol("xgboost", "EURUSD") is None


def test_save_champion_overwrites_previous(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    save_champion(_champion())
    updated = _champion()
    updated["score"] = 0.80

    save_champion(updated)

    loaded = load_champion("xgboost", "dollar_majors")
    assert loaded["score"] == 0.80


def test_champion_file_is_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    save_champion(_champion())

    path = tmp_path / "xgboost_dollar_majors.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "params" in data
    assert "promoted_at" in data
