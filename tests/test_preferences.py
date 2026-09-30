from teltonika_modbus_configurator.preferences import (
    DEFAULT_GATEWAY_HOST,
    load_last_gateway_host,
    save_last_gateway_host,
)


def test_gateway_host_defaults_when_preferences_do_not_exist(tmp_path):
    assert load_last_gateway_host(path=tmp_path / "missing.json") == DEFAULT_GATEWAY_HOST


def test_gateway_host_is_persisted_without_credentials(tmp_path):
    path = tmp_path / "preferences.json"

    save_last_gateway_host(" 10.33.24.1 ", path=path)

    assert load_last_gateway_host(path=path) == "10.33.24.1"
    text = path.read_text(encoding="utf-8")
    assert "password" not in text.lower()
    assert "username" not in text.lower()


def test_invalid_preferences_fall_back_to_default(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("not json", encoding="utf-8")

    assert load_last_gateway_host(path=path) == DEFAULT_GATEWAY_HOST
