import pytest

from teltonika_modbus_configurator.models import (
    FunctionCode, Project, Request, ServerMapping, TcpClientDevice
)
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project
from teltonika_modbus_configurator.validator import validate_project
from teltonika_modbus_configurator.yaml_writer import dump_project
from teltonika_modbus_configurator.loader import load_project


CLIENT = """package modbus_client

config main 'main'
\toption enabled '1'

config tcp_server '5'
\toption name 'ChillerTCP'
\toption server_id '117'
\toption ip '10.33.22.50'
\toption port '502'
\toption timeout '5'
\toption period '10'
\toption frequency 'period'
\toption enabled '1'

config request_5 '6'
\toption name 'Status_Temp'
\toption enabled '1'
\toption function '4'
\toption data_type '16bit_int_hi_first'
\toption reg_count '1'
\toption first_reg '10'
"""

SERVER = """package modbus_server

config modbus 'modbus'
\toption keepconn '1'
\toption port '502'
\toption device_id '102'
\toption enabled '1'

config tag '1'
\toption tag_name 'ChillerTCP_Temp'
\toption tag_source 'modbus_client'
\toption tag_permissions 'r'
\toption modbus_reg_num '1200'
\toption modbus_type '4'
\toption tag_id '5.6'
\toption enabled '1'
\toption tag_type 'int16'
\toption tag_count '1'
"""


def test_active_tcp_client_import_is_modeled_and_lossless():
    project = import_project(CLIENT, SERVER)
    assert len(project.tcp_clients) == 1
    client = project.tcp_clients[0]
    assert client.name == "ChillerTCP"
    assert client.server_id == 117
    assert client.host == "10.33.22.50"
    assert client.port == 502
    assert client.source_id == "5"
    assert client.raw_options["frequency"] == "period"
    assert client.requests[0].name == "Status_Temp"
    assert client.requests[0].function == FunctionCode.READ_INPUT_REGISTERS
    assert client.requests[0].source_id == "6"
    assert project.mappings[0].device == "ChillerTCP"
    assert project.mappings[0].request == "Status_Temp"
    assert validate_project(project) == []

    generated = generate_uci(project)
    assert generated.modbus_client == CLIENT
    assert generated.modbus_server == SERVER


def test_tcp_client_yaml_roundtrip_preserves_source(tmp_path):
    project = import_project(CLIENT, SERVER)
    path = tmp_path / "mixed.yaml"
    path.write_text(dump_project(project), encoding="utf-8")
    loaded = load_project(path)
    assert loaded.tcp_clients == project.tcp_clients
    generated = generate_uci(loaded)
    assert generated.modbus_client == CLIENT
    assert generated.modbus_server == SERVER


def test_fresh_tcp_client_generation_waits_for_verified_uci_schema():
    request = Request("Temp", FunctionCode.READ_INPUT_REGISTERS, 10)
    client = TcpClientDevice("ChillerTCP", server_id=117, host="10.33.22.50", requests=[request])
    mapping = ServerMapping("Temp", "ChillerTCP", "Temp", 1200, "input_register", permissions="r")
    project = Project(tcp_clients=[client], mappings=[mapping])
    assert validate_project(project) == []
    with pytest.raises(ValueError, match="Fresh Modbus TCP Client generation"):
        generate_uci(project)
