from teltonika_modbus_configurator.models import (
    Device,
    FunctionCode,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
)
from teltonika_modbus_configurator.validator import validate_project


def _project(register: int) -> Project:
    connection = SerialConnection(name="RS485")
    request = Request(
        name="IR",
        function=FunctionCode.READ_INPUT_REGISTERS,
        register=515,
    )
    device = Device(
        name="Device01",
        slave_id=1,
        connection="RS485",
        requests=[request],
    )
    mapping = ServerMapping(
        name="Device01_Temp",
        device="Device01",
        request="IR",
        register=register,
        register_type="input_register",
    )
    return Project(connections=[connection], devices=[device], mappings=[mapping])


def test_tcp_register_lower_bound_is_valid():
    assert validate_project(_project(1025)) == []


def test_tcp_register_upper_bound_is_valid():
    assert validate_project(_project(65536)) == []


def test_tcp_register_below_teltonika_range_is_rejected():
    messages = validate_project(_project(1024))
    assert any("TCP register must be 1025..65536" in m.message for m in messages)


def test_tcp_register_above_teltonika_range_is_rejected():
    messages = validate_project(_project(65537))
    assert any("TCP register must be 1025..65536" in m.message for m in messages)
