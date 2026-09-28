import pytest

from teltonika_modbus_configurator.first_project import (
    FirstProjectOptions,
    build_first_project,
    validate_first_project_options,
)


def test_build_tcp_first_project():
    options = FirstProjectOptions(
        project_type="tcp", tcp_device_name="Carel", tcp_host="192.168.2.20",
        tcp_unit_id=1, tcp_server_device_id=101,
    )
    project = build_first_project(options)

    assert project.connections == []
    assert project.devices == []
    assert len(project.tcp_clients) == 1
    assert (project.tcp_clients[0].name, project.tcp_clients[0].host) == ("Carel", "192.168.2.20")
    assert project.tcp_server.device_id == 101


def test_build_rtu_first_project():
    options = FirstProjectOptions(
        project_type="rtu", serial_name="Thermostats", baudrate=19200,
        parity="even", stopbits=1, rtu_device_name="RDF01", rtu_slave_id=1,
    )
    project = build_first_project(options)

    assert len(project.connections) == 1
    assert project.connections[0].name == "Thermostats"
    assert project.connections[0].parity == "even"
    assert len(project.devices) == 1
    assert project.devices[0].connection == "Thermostats"
    assert project.tcp_clients == []


def test_build_mixed_first_project():
    project = build_first_project(FirstProjectOptions(
        project_type="mixed", rtu_device_name="RDF01", tcp_device_name="Carel",
    ))

    assert len(project.connections) == 1
    assert len(project.devices) == 1
    assert len(project.tcp_clients) == 1


@pytest.mark.parametrize("changes, expected", [
    ({"tcp_server_device_id": 0}, "TCP Server Device ID"),
    ({"project_type": "tcp", "tcp_host": ""}, "host/IP"),
    ({"project_type": "rtu", "rtu_slave_id": 248}, "Slave ID"),
    ({"project_type": "mixed", "rtu_device_name": "Same", "tcp_device_name": "Same"}, "must be different"),
])
def test_first_project_validation(changes, expected):
    options = FirstProjectOptions(**changes)
    assert any(expected in error for error in validate_first_project_options(options))


def test_build_rejects_invalid_options():
    with pytest.raises(ValueError, match="TCP device host/IP"):
        build_first_project(FirstProjectOptions(project_type="tcp", tcp_host=""))
