from pathlib import Path

from teltonika_modbus_configurator.loader import load_project


def test_bulk_template_expands_devices_and_mappings(tmp_path: Path) -> None:
    config = tmp_path / "project.yaml"
    config.write_text(
        """
connections:
  - name: RS485

templates:
  sensor:
    requests:
      - name: Value
        function: 4
        register: 100
    mappings:
      - name: "{device}_Value"
        request: Value
        register_type: input_register
        start_register: 1000

device_groups:
  - template: sensor
    connection: RS485
    name_pattern: "Sensor{index:02d}"
    count: 3
    slave_start: 10
""",
        encoding="utf-8",
    )

    project = load_project(config)

    assert [d.name for d in project.devices] == ["Sensor01", "Sensor02", "Sensor03"]
    assert [d.slave_id for d in project.devices] == [10, 11, 12]
    assert all(d.requests[0].name == "Value" for d in project.devices)
    assert [m.register for m in project.mappings] == [1000, 1001, 1002]
    assert [m.device for m in project.mappings] == ["Sensor01", "Sensor02", "Sensor03"]


def test_explicit_slave_ids_are_supported(tmp_path: Path) -> None:
    config = tmp_path / "project.yaml"
    config.write_text(
        """
connections:
  - name: RS485

templates:
  generic:
    requests:
      - name: Value
        function: 3
        register: 12

device_groups:
  - template: generic
    connection: RS485
    name_pattern: "Device{index}"
    count: 3
    slave_ids: [1, 44, 97]
""",
        encoding="utf-8",
    )

    project = load_project(config)
    assert [d.slave_id for d in project.devices] == [1, 44, 97]


def test_slave_id_count_must_match_group_count(tmp_path: Path) -> None:
    config = tmp_path / "project.yaml"
    config.write_text(
        """
connections:
  - name: RS485

templates:
  generic:
    requests: []

device_groups:
  - template: generic
    connection: RS485
    count: 3
    slave_ids: [1, 2]
""",
        encoding="utf-8",
    )

    try:
        load_project(config)
    except ValueError as exc:
        assert "slave_ids length must equal count" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
