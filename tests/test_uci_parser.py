import pytest

from teltonika_modbus_configurator.loader import load_project
from teltonika_modbus_configurator.models import Device, FunctionCode, Request, ServerMapping
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project, parse_uci
from teltonika_modbus_configurator.yaml_writer import dump_project


CLIENT = """package modbus_client

config main 'main'
\toption debug '0'
\toption enabled '1'

config rtu_device '1'
\toption device '/dev/rs485'
\toption baudrate '19200'
\toption databits '8'
\toption parity 'none'
\toption name 'VeterinaTEST'
\toption stopbits '2'
\toption enabled '1'

config rtu_server '2'
\toption server_id '24'
\toption rtu_device '1'
\toption timeout '1'
\toption period '10'
\toption frequency 'period'
\toption name 'TEST01'
\toption enabled '0'

config request_2 '3'
\toption name 'IR_TEST'
\toption enabled '0'
\toption function '4'
\toption data_type '16bit_int_hi_first'
\toption reg_count '1'
\toption first_reg '515'
"""

SERVER = """package modbus_server

config modbus 'modbus'
\toption keepconn '1'
\toption port '1502'
\toption device_id '77'
\toption enabled '1'

config tag '1'
\toption tag_name 'TEST01_IR'
\toption tag_source 'modbus_client'
\toption modbus_reg_num '1200'
\toption modbus_type '4'
\toption tag_id '2.3'
\toption enabled '0'
"""


def test_parse_uci_sections():
    sections = parse_uci(CLIENT)
    assert any(s.section_type == "rtu_device" and s.name == "1" for s in sections)
    assert any(s.section_type == "request_2" and s.name == "3" for s in sections)


def test_import_known_trb_structure():
    project = import_project(CLIENT, SERVER)
    assert project.connections[0].name == "VeterinaTEST"
    assert project.connections[0].source_id == "1"
    assert project.devices[0].name == "TEST01"
    assert project.devices[0].source_id == "2"
    assert project.devices[0].slave_id == 24
    assert project.devices[0].requests[0].source_id == "3"
    assert project.mappings[0].source_id == "1"
    assert project.mappings[0].register == 1200
    assert project.tcp_server.port == 1502
    assert project.tcp_server.device_id == 77


def test_import_zero_edit_generate_is_byte_exact():
    client = CLIENT + """
config tcp_server '5'
\toption server_id '1'
\toption port '502'
"""
    project = import_project(client, SERVER)
    generated = generate_uci(project)
    assert generated.modbus_client == client
    assert generated.modbus_server == SERVER


def test_import_dump_load_preserves_lossless_source(tmp_path):
    client = CLIENT + """
config tcp_server '5'
\toption server_id '1'
\toption port '502'
"""
    imported = import_project(client, SERVER)
    yaml_path = tmp_path / "imported.yaml"
    yaml_path.write_text(dump_project(imported), encoding="utf-8")
    loaded = load_project(yaml_path)
    generated = generate_uci(loaded)
    assert generated.modbus_client == client
    assert generated.modbus_server == SERVER


def test_append_new_device_uses_ids_after_existing_stub_and_preserves_baseline():
    client = CLIENT + """
config tcp_server '5'
\toption server_id '1'
\toption port '502'
"""
    project = import_project(client, SERVER)
    project.devices.append(Device(name="PUSH_TEST", slave_id=25, connection="VeterinaTEST", enabled=False,
        requests=[Request(name="IR_TEST", function=FunctionCode.READ_INPUT_REGISTERS, register=515, enabled=False)]))
    project.mappings.append(ServerMapping(name="PUSH_TEST_IR", device="PUSH_TEST", request="IR_TEST", register=1201,
                                          register_type="input_register", enabled=False))
    generated = generate_uci(project)
    assert "config rtu_server '6'" in generated.modbus_client
    assert "config request_6 '7'" in generated.modbus_client
    assert "config tag '2'" in generated.modbus_server
    assert "option tag_id '6.7'" in generated.modbus_server


def test_editing_imported_device_preserves_its_uci_id():
    project = import_project(CLIENT, SERVER)
    project.devices[0].slave_id = 99
    project.devices[0].name = "RENAMED"
    project.mappings[0].device = "RENAMED"
    generated = generate_uci(project)
    assert "config rtu_server '2'" in generated.modbus_client
    assert "option server_id '99'" in generated.modbus_client
    assert "option name 'RENAMED'" in generated.modbus_client
    assert "option tag_id '2.3'" in generated.modbus_server


def test_add_request_to_existing_imported_device_allocates_child_id():
    project = import_project(CLIENT, SERVER)
    project.devices[0].requests.append(Request(name="CMD", function=FunctionCode.WRITE_SINGLE_HOLDING_REGISTER,
                                               register=101, values="1", enabled=False))
    project.mappings.append(ServerMapping(name="CMD", device="TEST01", request="CMD", register=1201,
                                          register_type="holding_register", permissions="w"))
    generated = generate_uci(project)
    assert "config request_2 '4'" in generated.modbus_client
    assert "option function '6'" in generated.modbus_client
    assert "option first_reg '101'" in generated.modbus_client
    assert "config tag '2'" in generated.modbus_server
    assert "option tag_id '2.4'" in generated.modbus_server


def test_delete_imported_mapping_and_request_removes_only_their_sections():
    project = import_project(CLIENT, SERVER)
    project.mappings.clear()
    project.devices[0].requests.clear()
    generated = generate_uci(project)
    assert "config rtu_server '2'" in generated.modbus_client
    assert "config request_2 '3'" not in generated.modbus_client
    assert "config tag '1'" not in generated.modbus_server


def test_repeat_generation_with_new_items_is_deterministic():
    project = import_project(CLIENT, SERVER)
    project.devices[0].requests.append(Request(name="EXTRA", function=FunctionCode.READ_HOLDING_REGISTERS, register=101))
    first = generate_uci(project)
    second = generate_uci(project)
    assert first == second


def test_empty_tcp_client_stub_is_safe_to_import():
    client = CLIENT + """
config tcp_server '5'
\toption server_id '1'
\toption port '502'
"""
    project = import_project(client, SERVER)
    assert project.devices[0].name == "TEST01"
    assert len(project.tcp_clients) == 1
    assert project.tcp_clients[0].source_id == "5"


def test_active_tcp_client_is_modeled_in_v03():
    client = CLIENT + """
config tcp_server '5'
\toption name 'TCP_DEVICE'
\toption server_id '1'
\toption ip '192.168.1.50'
\toption port '502'

config request_5 '6'
\toption name 'TCP_IR'
\toption function '4'
\toption data_type '16bit_int_hi_first'
\toption reg_count '1'
\toption first_reg '10'
"""
    project = import_project(client, SERVER)
    assert len(project.tcp_clients) == 1
    assert project.tcp_clients[0].name == "TCP_DEVICE"
    assert project.tcp_clients[0].host == "192.168.1.50"
    assert project.tcp_clients[0].requests[0].name == "TCP_IR"
    generated = generate_uci(project)
    assert generated.modbus_client == client
