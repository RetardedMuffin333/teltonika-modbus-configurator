from teltonika_modbus_configurator.models import TcpClientDevice


def test_tcp_client_server_id_is_exposed_as_unit_id():
    device = TcpClientDevice(name="Imported", server_id=7)
    assert device.server_id == 7
    assert device.unit_id == 7


def test_tcp_client_unit_id_constructor_updates_server_id():
    device = TcpClientDevice(name="GUI", unit_id=9)
    assert device.unit_id == 9
    assert device.server_id == 9


def test_tcp_client_unit_id_edit_stays_in_sync():
    device = TcpClientDevice(name="GUI", server_id=1)
    device.unit_id = 11
    assert device.unit_id == 11
    assert device.server_id == 11

    device.server_id = 12
    assert device.server_id == 12
    assert device.unit_id == 12
