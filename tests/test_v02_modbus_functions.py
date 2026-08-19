from teltonika_modbus_configurator.models import (
    Device, FunctionCode, Project, Request, SerialConnection, ServerMapping
)
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project
from teltonika_modbus_configurator.validator import validate_project


def base_project(request: Request, mapping: ServerMapping) -> Project:
    return Project(
        connections=[SerialConnection("RS485")],
        devices=[Device("D1", 1, "RS485", requests=[request])],
        mappings=[mapping],
    )


def test_fc06_write_only_mapping_generation():
    request = Request(
        "CMD_WorkMode", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, 101,
        data_type="int16", byte_order="high_byte_first", enabled=False, values="4",
    )
    mapping = ServerMapping(
        "CMD_WorkMode", "D1", "CMD_WorkMode", 1200, "holding_register",
        enabled=True, permissions="w", data_type="int16", count=1,
    )
    project = base_project(request, mapping)
    assert validate_project(project) == []
    uci = generate_uci(project)
    assert "option function '6'" in uci.modbus_client
    assert "option reg_count '4'" in uci.modbus_client
    assert "option enabled '0'" in uci.modbus_client
    assert "option tag_permissions 'w'" in uci.modbus_server
    assert "option modbus_type '3'" in uci.modbus_server


def test_fc05_coil_mapping_generation():
    request = Request(
        "CMD_Enable", FunctionCode.WRITE_SINGLE_COIL, 32,
        data_type="bool", byte_order="none", values="1",
    )
    mapping = ServerMapping(
        "CMD_Enable", "D1", "CMD_Enable", 1201, "coil",
        permissions="w", data_type="bool",
    )
    project = base_project(request, mapping)
    assert validate_project(project) == []
    uci = generate_uci(project)
    assert "option function '5'" in uci.modbus_client
    assert "option data_type 'bool'" in uci.modbus_client
    assert "option modbus_type '1'" in uci.modbus_server


def test_direction_and_register_area_validation():
    request = Request("R", FunctionCode.READ_INPUT_REGISTERS, 515)
    mapping = ServerMapping("M", "D1", "R", 1200, "holding_register", permissions="w")
    messages = validate_project(base_project(request, mapping))
    text = "\n".join(m.message for m in messages)
    assert "does not match FC04" in text
    assert "cannot be exposed Write-Only" in text


def test_write_request_import_uses_values_not_count():
    client = """package modbus_client
config rtu_device '1'
 option name 'RS485'
 option device '/dev/rs485'
config rtu_server '2'
 option name 'D1'
 option server_id '1'
 option rtu_device '1'
config request_2 '3'
 option name 'CMD'
 option function '6'
 option data_type '16bit_int_hi_first'
 option first_reg '101'
 option reg_count '4'
 option enabled '0'
"""
    server = """package modbus_server
config modbus 'modbus'
 option device_id '101'
config tag '1'
 option tag_name 'CMD'
 option tag_source 'modbus_client'
 option tag_id '2.3'
 option modbus_reg_num '1200'
 option modbus_type '3'
 option tag_permissions 'w'
 option tag_type 'int16'
 option tag_count '1'
"""
    project = import_project(client, server)
    request = project.devices[0].requests[0]
    assert request.count == 1
    assert request.values == "4"
    assert project.mappings[0].permissions == "w"
