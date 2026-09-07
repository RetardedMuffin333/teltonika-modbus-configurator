from teltonika_modbus_configurator.gui_deploy import format_elapsed_time


def test_format_elapsed_time_seconds() -> None:
    assert format_elapsed_time(8.4) == "8 s"


def test_format_elapsed_time_minutes() -> None:
    assert format_elapsed_time(198.2) == "3 min 18 s"


def test_format_elapsed_time_hours() -> None:
    assert format_elapsed_time(3723.0) == "1 h 2 min 3 s"
