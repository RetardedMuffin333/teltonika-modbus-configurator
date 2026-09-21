from teltonika_modbus_configurator.models import (
    FunctionCode,
    Project,
    Request,
    ServerMapping,
    TcpClientDevice,
)
from teltonika_modbus_configurator.project_report import render_project_report


def _batched_project() -> Project:
    return Project(
        tcp_clients=[TcpClientDevice(
            name="TP",
            host="192.168.2.20",
            requests=[
                Request("Batch_FC03_1_4", FunctionCode.READ_HOLDING_REGISTERS, 1, count=4, data_type="uint16"),
                Request("Setpoint_w", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, 10, enabled=False, values="0"),
            ],
        )],
        mappings=[
            ServerMapping("Batch_FC03_1_4", "TP", "Batch_FC03_1_4", 1025, "holding_register", count=4, data_type="uint16", export_symbol=False),
            ServerMapping("Temperature", "TP", "Batch_FC03_1_4", 1025, "holding_register", deploy=False, symbol_data_type="float32"),
            ServerMapping("Setpoint", "TP", "Batch_FC03_1_4", 1027, "holding_register", deploy=False, symbol_data_type="int16", source_offset=2),
            ServerMapping("Setpoint_w", "TP", "Setpoint_w", 20000, "holding_register", permissions="w"),
        ],
    )


def test_report_summarizes_batching_workload_and_address_blocks():
    report = render_project_report(_batched_project(), project_name="plant.yaml")

    assert "Project: plant.yaml" in report
    assert "Modbus TCP client devices:      1" in report
    assert "Enabled cyclic read requests:   1" in report
    assert "Disabled SCADA write requests:  1" in report
    assert "Logical exported symbols:       3" in report
    assert "Physical batch requests:        1" in report
    assert "Logical symbols inside batches: 2" in report
    assert "Estimated requests avoided:     1" in report
    assert "Holding Registers: 1025-1028, 20000 (5 addresses)" in report
    assert "TP [TCP]: 1 cyclic reads, 0 cyclic writes, 2 deployed mappings" in report
    assert "OK: No write requests are enabled for cyclic execution." in report


def test_report_highlights_enabled_write_request():
    project = _batched_project()
    project.tcp_clients[0].requests[1].enabled = True

    report = render_project_report(project)

    assert "WARNING: 1 write request(s) are enabled for cyclic execution." in report
    assert "TP/Setpoint_w (FC06)" in report


def test_empty_project_report_is_still_useful():
    report = render_project_report(Project())

    assert "No source devices configured." in report
    assert "Coils: none" in report
    assert "Errors:   0" in report
