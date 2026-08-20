from teltonika_modbus_configurator.models import FunctionCode, Project, Request, ServerMapping, TcpClientDevice
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.uci_parser import import_project


LIVE_CLIENT = """package modbus_client

config main 'main'
\toption enabled '1'
\toption debug '0'

config tcp_server '15'
\toption timeout '5'
\toption server_id '1'
\toption frequency 'period'
\toption port '502'
\toption dev_ipaddr '10.33.24.5'
\toption name 'TCP_Test'
\toption delay '0'
\toption skip_on_many_tmos '0'
\toption enabled '0'
\toption period '10'
\toption reconnect '0'

config request_15 '16'
\toption data_type '16bit_int_hi_first'
\toption no_brackets '0'
\toption enabled '0'
\toption store_on_change_only '0'
\toption broadcast '0'
\toption name 'IR_TCP_Test'
\toption reg_count '1'
\toption first_reg '10'
\toption function '4'
"""

LIVE_SERVER = """package modbus_server

config modbus 'modbus'
\toption keepconn '1'
\toption port '502'
\toption device_id '1'
\toption enabled '1'
"""


def test_live_tcp_client_import_reads_dev_ipaddr():
    project = import_project(LIVE_CLIENT, LIVE_SERVER)
    tcp = project.tcp_clients[0]
    assert tcp.name == "TCP_Test"
    assert tcp.host == "10.33.24.5"
    assert tcp.server_id == 1
    assert tcp.unit_id == 1
    assert tcp.port == 502
    assert tcp.period == 10
    assert tcp.timeout == 5
    assert tcp.requests[0].name == "IR_TCP_Test"


def test_live_tcp_client_zero_edit_is_byte_exact():
    project = import_project(LIVE_CLIENT, LIVE_SERVER)
    generated = generate_uci(project)
    assert generated.modbus_client == LIVE_CLIENT
    assert generated.modbus_server == LIVE_SERVER


def test_edit_live_tcp_client_preserves_unmodeled_options():
    project = import_project(LIVE_CLIENT, LIVE_SERVER)
    tcp = project.tcp_clients[0]
    tcp.host = "10.33.24.6"
    tcp.period = 20
    generated = generate_uci(project)
    assert "option dev_ipaddr '10.33.24.6'" in generated.modbus_client
    assert "option period '20'" in generated.modbus_client
    assert "option delay '0'" in generated.modbus_client
    assert "option reconnect '0'" in generated.modbus_client
    assert "config tcp_server '15'" in generated.modbus_client
    assert "config request_15 '16'" in generated.modbus_client


def test_add_request_to_imported_tcp_client_allocates_child_id():
    project = import_project(LIVE_CLIENT, LIVE_SERVER)
    tcp = project.tcp_clients[0]
    tcp.requests.append(Request(
        name="HR_TCP_Test",
        function=FunctionCode.READ_HOLDING_REGISTERS,
        register=20,
        count=1,
        enabled=False,
    ))
    generated = generate_uci(project)
    assert "config request_15 '17'" in generated.modbus_client
    assert "option name 'HR_TCP_Test'" in generated.modbus_client
    assert "option function '3'" in generated.modbus_client


def test_fresh_tcp_client_uses_verified_rutos_schema_and_mapping():
    project = Project(
        tcp_clients=[TcpClientDevice(
            name="TCP_Test",
            server_id=1,
            host="10.33.24.5",
            port=502,
            period=10,
            timeout=5,
            enabled=False,
            requests=[Request(
                name="IR_TCP_Test",
                function=FunctionCode.READ_INPUT_REGISTERS,
                register=10,
                count=1,
                enabled=False,
            )],
        )],
        mappings=[ServerMapping(
            name="TCP_Test_IR",
            device="TCP_Test",
            request="IR_TCP_Test",
            register=1025,
            register_type="input_register",
            permissions="r",
            enabled=False,
        )],
    )
    generated = generate_uci(project)
    client = generated.modbus_client
    server = generated.modbus_server
    assert "config tcp_server '1'" in client
    assert "option timeout '5'" in client
    assert "option server_id '1'" in client
    assert "option frequency 'period'" in client
    assert "option port '502'" in client
    assert "option dev_ipaddr '10.33.24.5'" in client
    assert "option name 'TCP_Test'" in client
    assert "option delay '0'" in client
    assert "option skip_on_many_tmos '0'" in client
    assert "option enabled '0'" in client
    assert "option period '10'" in client
    assert "option reconnect '0'" in client
    assert "config request_1 '2'" in client
    assert "option name 'IR_TCP_Test'" in client
    assert "option first_reg '10'" in client
    assert "option function '4'" in client
    assert "option tag_id '1.2'" in server
