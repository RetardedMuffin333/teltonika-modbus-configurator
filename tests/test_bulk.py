import pytest

from teltonika_modbus_configurator.bulk import (
    BYTE_ORDERS_BY_TYPE,
    BulkMappingSpec,
    BulkRequestSpec,
    BulkSpec,
    apply_bulk,
    generate_bulk,
    suggested_register_type,
    validate_bulk_spec,
)
from teltonika_modbus_configurator.models import (
    Device,
    FunctionCode,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
)


def base_project() -> Project:
    return Project(connections=[SerialConnection(name="RS485_Main")])


def room_spec(count=3) -> BulkSpec:
    return BulkSpec(
        connection="RS485_Main",
        name_pattern="Room{index:02d}",
        count=count,
        start_index=1,
        slave_start=1,
        requests=[
            BulkRequestSpec("Temp", FunctionCode.READ_INPUT_REGISTERS, 515),
            BulkRequestSpec("SetP", FunctionCode.READ_INPUT_REGISTERS, 554),
            BulkRequestSpec("Cmd", FunctionCode.READ_HOLDING_REGISTERS, 262),
        ],
        mappings=[
            BulkMappingSpec("{device}_Temp", "Temp", "input_register", 1025),
            BulkMappingSpec("{device}_SetP", "SetP", "input_register", 1050),
            BulkMappingSpec("HR_{device}", "Cmd", "holding_register", 1080),
        ],
    )


def test_generate_generic_bulk_devices_and_mappings():
    project = base_project()
    result = generate_bulk(project, room_spec())
    assert [d.name for d in result.devices] == ["Room01", "Room02", "Room03"]
    assert [d.slave_id for d in result.devices] == [1, 2, 3]
    assert [r.name for r in result.devices[0].requests] == ["Temp", "SetP", "Cmd"]
    input_regs = [m.register for m in result.mappings if m.register_type == "input_register"]
    holding_regs = [m.register for m in result.mappings if m.register_type == "holding_register"]
    assert input_regs == [1025, 1050, 1026, 1051, 1027, 1052]
    assert holding_regs == [1080, 1081, 1082]


def test_apply_bulk_is_atomic_and_appends_on_success():
    project = base_project()
    result = apply_bulk(project, room_spec(2))
    assert len(result.devices) == 2
    assert len(project.devices) == 2
    assert len(project.mappings) == 6


def test_duplicate_slave_id_on_same_connection_is_rejected():
    project = base_project(); project.devices.append(Device("Existing", 1, "RS485_Main"))
    errors = validate_bulk_spec(project, room_spec(2))
    assert any("Slave ID 1 is already used" in e for e in errors)


def test_duplicate_device_name_is_rejected():
    project = base_project(); project.devices.append(Device("Room02", 40, "RS485_Main"))
    errors = validate_bulk_spec(project, room_spec(3))
    assert any("Room02" in e and "already exists" in e for e in errors)


def test_mapping_overlap_is_rejected():
    project = base_project()
    project.devices.append(Device("Existing", 99, "RS485_Main", requests=[Request("Temp", FunctionCode.READ_INPUT_REGISTERS, 515, count=2)]))
    project.mappings.append(ServerMapping("ExistingTemp", "Existing", "Temp", 1026, "input_register"))
    errors = validate_bulk_spec(project, room_spec(3))
    assert any("overlaps existing mapping" in e for e in errors)


def test_explicit_slave_ids_are_supported():
    project = base_project(); spec = room_spec(3); spec.slave_ids = [1, 44, 97]
    result = generate_bulk(project, spec)
    assert [d.slave_id for d in result.devices] == [1, 44, 97]


def test_invalid_mapping_request_fails_before_generation():
    project = base_project(); spec = room_spec(1)
    spec.mappings.append(BulkMappingSpec("X", "Missing", "input_register", 2000))
    with pytest.raises(ValueError, match="unknown request"):
        generate_bulk(project, spec)


@pytest.mark.parametrize("dtype", ["int32", "uint32", "float32"])
@pytest.mark.parametrize("order", ["1234", "2143", "3412", "4321"])
def test_bulk_accepts_verified_32bit_matrix(dtype, order):
    project = base_project()
    spec = BulkSpec(
        connection="RS485_Main", name_pattern="D{index}", count=1,
        requests=[BulkRequestSpec("Value", FunctionCode.READ_INPUT_REGISTERS, 20, data_type=dtype, byte_order=order)],
        mappings=[BulkMappingSpec("{device}_Value", "Value", "input_register", 1200, data_type=dtype)],
    )
    assert validate_bulk_spec(project, spec) == []
    result = generate_bulk(project, spec)
    assert result.devices[0].requests[0].data_type == dtype
    assert result.devices[0].requests[0].byte_order == order


def test_bulk_rejects_invalid_32bit_byte_order():
    project = base_project()
    spec = BulkSpec(connection="RS485_Main", name_pattern="D{index}", count=1,
                    requests=[BulkRequestSpec("Value", FunctionCode.READ_INPUT_REGISTERS, 20, data_type="float32", byte_order="high_byte_first")])
    assert any("byte order" in error for error in validate_bulk_spec(project, spec))


def test_supported_byte_order_matrix_is_explicit():
    assert BYTE_ORDERS_BY_TYPE["int16"] == {"high_byte_first", "low_byte_first"}
    assert BYTE_ORDERS_BY_TYPE["float32"] == {"1234", "2143", "3412", "4321"}


@pytest.mark.parametrize("fc, expected", [
    (FunctionCode.READ_COILS, "coil"),
    (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input"),
    (FunctionCode.READ_HOLDING_REGISTERS, "holding_register"),
    (FunctionCode.READ_INPUT_REGISTERS, "input_register"),
    (FunctionCode.WRITE_SINGLE_COIL, "coil"),
    (FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, "holding_register"),
    (FunctionCode.WRITE_MULTIPLE_COILS, "coil"),
    (FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS, "holding_register"),
])
def test_suggested_tcp_area_matches_function(fc, expected):
    assert suggested_register_type(fc) == expected


def test_bulk_rejects_wrong_tcp_area_for_write_request():
    project = base_project()
    spec = BulkSpec(
        connection="RS485_Main", name_pattern="D{index}", count=1,
        requests=[BulkRequestSpec("Cmd", FunctionCode.WRITE_SINGLE_COIL, 10, data_type="bool", byte_order="none", values="1")],
        mappings=[BulkMappingSpec("{device}_Cmd", "Cmd", "holding_register", 1200, data_type="bool")],
    )
    assert any("must use TCP type 'coil'" in error for error in validate_bulk_spec(project, spec))
