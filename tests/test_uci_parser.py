from teltonika_modbus_configurator.loader import load_project
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
    assert project.devices[0].name == "TEST01"
    assert project.devices[0].slave_id == 24
    assert project.devices[0].enabled is False
    assert project.devices[0].requests[0].name == "IR_TEST"
    assert project.devices[0].requests[0].register == 515
    assert project.mappings[0].name == "TEST01_IR"
    assert project.mappings[0].device == "TEST01"
    assert project.mappings[0].request == "IR_TEST"
    assert project.mappings[0].register == 1200
    assert project.tcp_server.port == 1502
    assert project.tcp_server.device_id == 77


def test_import_dump_load_generate_round_trip(tmp_path):
    imported = import_project(CLIENT, SERVER)
    yaml_path = tmp_path / "imported.yaml"
    yaml_path.write_text(dump_project(imported), encoding="utf-8")

    loaded = load_project(yaml_path)
    generated = generate_uci(loaded)

    assert "option port '1502'" in generated.modbus_server
    assert "option device_id '77'" in generated.modbus_server
    assert "config rtu_server '2'" in generated.modbus_client
    assert "config request_2 '3'" in generated.modbus_client
    assert "option tag_id '2.3'" in generated.modbus_server
