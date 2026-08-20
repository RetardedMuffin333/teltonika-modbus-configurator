import pytest

from teltonika_modbus_configurator.bulk import (
    BulkMappingSpec, BulkRequestSpec, BulkSpec, apply_bulk, generate_bulk,
    suggested_register_type, validate_bulk_spec,
)
from teltonika_modbus_configurator.models import Device, FunctionCode, Project, Request, SerialConnection, ServerMapping


def base_project() -> Project:
    return Project(connections=[SerialConnection(name="RS485_Main")])


def room_spec(count=3) -> BulkSpec:
    return BulkSpec(connection="RS485_Main", name_pattern="Room{index:02d}", count=count, start_index=1, slave_start=1,
        requests=[BulkRequestSpec("Temp", FunctionCode.READ_INPUT_REGISTERS, 515), BulkRequestSpec("SetP", FunctionCode.READ_INPUT_REGISTERS, 554), BulkRequestSpec("Cmd", FunctionCode.READ_HOLDING_REGISTERS, 262)],
        mappings=[BulkMappingSpec("{device}_Temp", "Temp", "input_register", 1025), BulkMappingSpec("{device}_SetP", "SetP", "input_register", 1050), BulkMappingSpec("HR_{device}", "Cmd", "holding_register", 1080)])


def test_generate_generic_bulk_devices_and_mappings():
    result = generate_bulk(base_project(), room_spec())
    assert [d.name for d in result.devices] == ["Room01", "Room02", "Room03"]
    assert [d.slave_id for d in result.devices] == [1, 2, 3]
    assert [r.name for r in result.devices[0].requests] == ["Temp", "SetP", "Cmd"]
    assert [m.register for m in result.mappings if m.register_type == "input_register"] == [1025, 1050, 1026, 1051, 1027, 1052]
    assert [m.register for m in result.mappings if m.register_type == "holding_register"] == [1080, 1081, 1082]


def test_apply_bulk_is_atomic_and_appends_on_success():
    project = base_project(); result = apply_bulk(project, room_spec(2))
    assert len(result.devices) == 2 and len(project.devices) == 2 and len(project.mappings) == 6


def test_duplicate_slave_id_on_same_connection_is_rejected():
    project = base_project(); project.devices.append(Device("Existing", 1, "RS485_Main"))
    assert any("Slave ID 1 is already used" in e for e in validate_bulk_spec(project, room_spec(2)))


def test_duplicate_device_name_is_rejected():
    project = base_project(); project.devices.append(Device("Room02", 40, "RS485_Main"))
    assert any("Room02" in e and "already exists" in e for e in validate_bulk_spec(project, room_spec(3)))


def test_mapping_overlap_is_rejected():
    project = base_project(); project.devices.append(Device("Existing", 99, "RS485_Main", requests=[Request("Temp", FunctionCode.READ_INPUT_REGISTERS, 515, count=2)]))
    project.mappings.append(ServerMapping("ExistingTemp", "Existing", "Temp", 1026, "input_register"))
    assert any("overlaps existing mapping" in e for e in validate_bulk_spec(project, room_spec(3)))


def test_explicit_slave_ids_are_supported():
    spec = room_spec(3); spec.slave_ids = [1, 44, 97]
    assert [d.slave_id for d in generate_bulk(base_project(), spec).devices] == [1, 44, 97]


def test_invalid_mapping_request_fails_before_generation():
    spec = room_spec(1); spec.mappings.append(BulkMappingSpec("X", "Missing", "input_register", 2000))
    with pytest.raises(ValueError, match="unknown request"): generate_bulk(base_project(), spec)


def test_32bit_datatypes_and_byte_orders_are_valid_in_bulk():
    spec = BulkSpec(connection="RS485_Main", name_pattern="Meter{index}", count=1, requests=[
        BulkRequestSpec("Power", FunctionCode.READ_INPUT_REGISTERS, 10, data_type="float32", byte_order="4321"),
        BulkRequestSpec("Counter", FunctionCode.READ_HOLDING_REGISTERS, 20, data_type="uint32", byte_order="2143"),
    ], mappings=[
        BulkMappingSpec("{device}_Power", "Power", "input_register", 2000, data_type="float32"),
        BulkMappingSpec("{device}_Counter", "Counter", "holding_register", 2100, data_type="uint32"),
    ])
    assert validate_bulk_spec(base_project(), spec) == []
    result = generate_bulk(base_project(), spec)
    assert result.devices[0].requests[0].data_type == "float32"
    assert result.devices[0].requests[0].byte_order == "4321"


def test_invalid_32bit_byte_order_is_rejected():
    spec = room_spec(1); spec.requests[0].data_type = "float32"; spec.requests[0].byte_order = "high_byte_first"
    assert any("invalid for float32" in e for e in validate_bulk_spec(base_project(), spec))


def test_write_requests_require_values_and_natural_tcp_area():
    spec = BulkSpec(connection="RS485_Main", name_pattern="Valve{index}", count=1,
        requests=[BulkRequestSpec("Open", FunctionCode.WRITE_SINGLE_COIL, 5, data_type="bool", byte_order="none", values="1")],
        mappings=[BulkMappingSpec("{device}_Open", "Open", "holding_register", 3000, data_type="bool")])
    errors = validate_bulk_spec(base_project(), spec)
    assert any("must use TCP type 'coil'" in e for e in errors)
    spec.mappings[0].register_type = "coil"
    assert validate_bulk_spec(base_project(), spec) == []


def test_suggested_register_type_covers_all_supported_functions():
    assert suggested_register_type(FunctionCode.READ_COILS) == "coil"
    assert suggested_register_type(FunctionCode.READ_DISCRETE_INPUTS) == "discrete_input"
    assert suggested_register_type(FunctionCode.READ_HOLDING_REGISTERS) == "holding_register"
    assert suggested_register_type(FunctionCode.READ_INPUT_REGISTERS) == "input_register"
    assert suggested_register_type(FunctionCode.WRITE_SINGLE_COIL) == "coil"
    assert suggested_register_type(FunctionCode.WRITE_SINGLE_HOLDING_REGISTER) == "holding_register"
    assert suggested_register_type(FunctionCode.WRITE_MULTIPLE_COILS) == "coil"
    assert suggested_register_type(FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS) == "holding_register"
