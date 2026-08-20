import pytest

from teltonika_modbus_configurator.models import FunctionCode, Project, Request, TcpClientDevice
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project
from teltonika_modbus_configurator.validator import validate_project


ORDERS = ("1234", "2143", "3412", "4321")
FAMILIES = (
    ("float32", "32bit_float"),
    ("int32", "32bit_int"),
    ("uint32", "32bit_uint"),
)


def _client_with_request(token: str) -> str:
    return f"""package modbus_client

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
\toption name 'IR_TCP_32bit'
\toption data_type '{token}'
\toption first_reg '25'
\toption reg_count '1'
\toption function '4'
"""


SERVER = """package modbus_server

config modbus 'modbus'
\toption keepconn '1'
\toption port '502'
\toption device_id '1'
\toption enabled '1'
"""


@pytest.mark.parametrize("data_type,prefix", FAMILIES)
@pytest.mark.parametrize("order", ORDERS)
def test_imports_verified_rutos_32bit_tokens(data_type, prefix, order):
    token = prefix + order
    client = _client_with_request(token)
    project = import_project(client, SERVER)
    request = project.tcp_clients[0].requests[0]
    assert request.data_type == data_type
    assert request.byte_order == order
    assert request.raw_data_type is None
    assert validate_project(project) == []
    generated = generate_uci(project)
    assert generated.modbus_client == client


@pytest.mark.parametrize("data_type,prefix", FAMILIES)
@pytest.mark.parametrize("order", ORDERS)
def test_fresh_32bit_requests_generate_verified_tokens(data_type, prefix, order):
    request = Request(
        "IR_TCP_32bit",
        FunctionCode.READ_INPUT_REGISTERS,
        25,
        count=1,
        data_type=data_type,
        byte_order=order,
        enabled=False,
    )
    project = Project(
        tcp_clients=[TcpClientDevice("TCP_Test2", server_id=2, host="10.33.24.5", enabled=False, requests=[request])]
    )
    assert validate_project(project) == []
    generated = generate_uci(project)
    assert f"option data_type '{prefix}{order}'" in generated.modbus_client


def test_32bit_wrong_byte_order_is_rejected():
    request = Request(
        "Bad32",
        FunctionCode.READ_INPUT_REGISTERS,
        25,
        data_type="float32",
        byte_order="high_byte_first",
    )
    project = Project(tcp_clients=[TcpClientDevice("TCP", requests=[request])])
    errors = [m.message for m in validate_project(project) if m.level == "error"]
    assert any("invalid byte order" in message for message in errors)
