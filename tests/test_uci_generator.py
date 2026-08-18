from pathlib import Path

from teltonika_modbus_configurator.loader import load_project
from teltonika_modbus_configurator.uci_generator import generate_uci
from teltonika_modbus_configurator.validator import validate_project


EXAMPLE = Path(__file__).parents[1] / "examples" / "basic.yaml"


def test_basic_example_validates():
    project = load_project(EXAMPLE)
    assert validate_project(project) == []


def test_basic_example_generates_proven_rutos_relationship():
    project = load_project(EXAMPLE)
    generated = generate_uci(project)

    assert "config rtu_device '1'" in generated.modbus_client
    assert "option name 'VeterinaTEST'" in generated.modbus_client

    assert "config rtu_server '2'" in generated.modbus_client
    assert "option name 'TEST01'" in generated.modbus_client
    assert "option enabled '0'" in generated.modbus_client

    assert "config request_2 '3'" in generated.modbus_client
    assert "option name 'IR_TEST'" in generated.modbus_client
    assert "option function '4'" in generated.modbus_client
    assert "option first_reg '515'" in generated.modbus_client

    assert "config tag '1'" in generated.modbus_server
    assert "option tag_name 'TEST01_IR'" in generated.modbus_server
    assert "option modbus_reg_num '1200'" in generated.modbus_server
    assert "option modbus_type '4'" in generated.modbus_server
    assert "option tag_id '2.3'" in generated.modbus_server
    assert "option enabled '0'" in generated.modbus_server


def test_tcp_server_defaults_match_tested_trb145_setup():
    project = load_project(EXAMPLE)
    generated = generate_uci(project)

    assert "option port '502'" in generated.modbus_server
    assert "option device_id '101'" in generated.modbus_server
    assert "option enabled '1'" in generated.modbus_server
