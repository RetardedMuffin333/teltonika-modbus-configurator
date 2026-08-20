from teltonika_modbus_configurator.models import FunctionCode, Project, Request, TcpClientDevice
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project
from teltonika_modbus_configurator.validator import validate_project


def test_imports_verified_rutos_float32_1234_token():
    client = """package modbus_client

config main 'main'
\toption enabled '1'

config tcp_server '17'
\toption timeout '1'
\toption server_id '2'
\toption frequency 'period'
\toption port '502'
\toption dev_ipaddr '10.33.24.5'
\toption name 'TCP_Test2'
\toption delay '0'
\toption skip_on_many_tmos '0'
\toption enabled '0'
\toption period '10'
\toption reconnect '0'

config request_17 '19'
\toption no_brackets '0'
\toption enabled '0'
\toption store_on_change_only '0'
\toption broadcast '0'
\toption name 'IR_TCP_Float'
\toption data_type '32bit_float1234'
\toption first_reg '25'
\toption reg_count '1'
\toption function '4'
"""
    server = """package modbus_server

config modbus 'modbus'
\toption keepconn '1'
\toption port '502'
\toption device_id '1'
\toption enabled '1'
"""
    project = import_project(client, server)
    request = project.tcp_clients[0].requests[0]
    assert request.data_type == "float32"
    assert request.byte_order == "1234"
    assert request.raw_data_type is None
    assert validate_project(project) == []
    generated = generate_uci(project)
    assert generated.modbus_client == client


def test_fresh_float32_1234_generates_verified_token():
    request = Request(
        "IR_TCP_Float",
        FunctionCode.READ_INPUT_REGISTERS,
        25,
        count=1,
        data_type="float32",
        byte_order="1234",
        enabled=False,
    )
    project = Project(
        tcp_clients=[TcpClientDevice("TCP_Test2", server_id=2, host="10.33.24.5", enabled=False, requests=[request])]
    )
    assert validate_project(project) == []
    generated = generate_uci(project)
    assert "option data_type '32bit_float1234'" in generated.modbus_client
