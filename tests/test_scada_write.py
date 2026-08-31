from teltonika_modbus_configurator.models import (
    Device,
    FunctionCode,
    Project,
    Request,
    ServerMapping,
    TcpClientDevice,
)
from teltonika_modbus_configurator.scada_write import allocate_scada_template_mapping_layout, create_scada_write_target
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.validator import validate_project


def _project():
    device = Device(
        name="RDF_Test", slave_id=1, connection="RDF400MB",
        requests=[Request(name="CMD_Oper_Mode", function=FunctionCode.READ_HOLDING_REGISTERS, register=101, count=1, data_type="int16", byte_order="high_byte_first", enabled=True)],
    )
    from teltonika_modbus_configurator.models import SerialConnection
    return Project(
        connections=[SerialConnection(name="RDF400MB")], devices=[device],
        mappings=[
            ServerMapping(name="CMD_Oper_Mode", device="RDF_Test", request="CMD_Oper_Mode", register=1031, register_type="holding_register", permissions="r", data_type="int16", count=1),
            ServerMapping(name="AI_U5_ZunTemp", device="RDF_Test", request="CMD_Oper_Mode", register=1100, register_type="holding_register", permissions="r", data_type="float32", count=1, enabled=False),
        ],
    )


def test_create_scada_write_target_is_disabled_fc06_and_separate_write_mapping():
    project = _project()
    target = create_scada_write_target(project, device_name="RDF_Test", read_request_name="CMD_Oper_Mode")
    assert target.request.name == "CMD_Oper_Mode_w"
    assert target.request.function == FunctionCode.WRITE_SINGLE_HOLDING_REGISTER
    assert target.request.register == 101
    assert target.request.enabled is False
    assert target.request.values == "0"
    assert target.mapping.register == 1200
    assert target.mapping.register_type == "holding_register"
    assert target.mapping.permissions == "w"
    assert target.mapping.enabled is True
    assert not [m for m in validate_project(project) if m.level == "error"]


def test_generated_uci_uses_disabled_fc06_and_write_only_tag():
    project = _project()
    create_scada_write_target(project, device_name="RDF_Test", read_request_name="CMD_Oper_Mode")
    uci = generate_uci(project)
    assert "option function '6'" in uci.modbus_client
    assert "option enabled '0'" in uci.modbus_client
    assert "option reg_count '0'" in uci.modbus_client
    assert "option tag_name 'CMD_Oper_Mode_w'" in uci.modbus_server
    assert "option tag_permissions 'w'" in uci.modbus_server
    assert "option modbus_reg_num '1200'" in uci.modbus_server


def test_carel_coil_feedback_creates_disabled_fc05_write_target():
    project = Project(
        tcp_clients=[TcpClientDevice(
            name="Carel_Test", host="192.168.2.20", port=502, server_id=1,
            requests=[Request(name="VKLOP_SISTEMA", function=FunctionCode.READ_COILS, register=8, count=1, data_type="bool", byte_order="none", enabled=True)],
        )],
        mappings=[ServerMapping(name="VKLOP_SISTEMA", device="Carel_Test", request="VKLOP_SISTEMA", register=1025, register_type="coil", permissions="r", data_type="bool", count=1)],
    )
    target = create_scada_write_target(project, device_name="Carel_Test", read_request_name="VKLOP_SISTEMA")
    assert target.request.name == "VKLOP_SISTEMA_w"
    assert target.request.function == FunctionCode.WRITE_SINGLE_COIL
    assert target.request.register == 8
    assert target.request.enabled is False
    assert target.request.values == "0"
    assert target.mapping.register_type == "coil"
    assert target.mapping.register == 1200
    assert target.mapping.permissions == "w"


def test_bulk_layout_keeps_read_and_write_holding_blocks_separate():
    project = _project()
    target = create_scada_write_target(project, device_name="RDF_Test", read_request_name="CMD_Oper_Mode")
    layout = allocate_scada_template_mapping_layout(project, [target.feedback_mapping, target.mapping])
    assert layout["CMD_Oper_Mode"] == (1032, 1)
    assert layout["CMD_Oper_Mode_w"] == (1201, 1)
