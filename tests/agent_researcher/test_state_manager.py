from src.agent_researcher.state_manager import StateManager, hash_filters


def test_hash_filters_is_order_independent():
    left = {"symbol": "XAUUSD", "hour_utc": (14, 15)}
    right = {"hour_utc": [14, 15], "symbol": "XAUUSD"}

    assert hash_filters(left) == hash_filters(right)


def test_state_tracks_holdout_once(tmp_path):
    state = StateManager(tmp_path / "agent" / "state.json", enforce_boundary=False)
    filters = {"symbol": "XAUUSD", "confidence_min": 0.85}
    filter_hash = hash_filters(filters)

    assert not state.has_used_holdout(filter_hash)

    state.mark_holdout_used(filter_hash, filters, "PROMISING")

    reloaded = StateManager(
        tmp_path / "agent" / "state.json",
        enforce_boundary=False,
    )
    assert reloaded.has_used_holdout(filter_hash)
