from teltonika_modbus_configurator.models import (
    Device,
    FunctionCode,
    Project,
    Request,
    ServerMapping,
)
from teltonika_modbus_configurator.register_allocator import next_free_register


def _project():
    devices = []
    mappings = []
    for i in range(1, 24):
        name = f"Joy{i:02d}"
        devices.append(
            Device(
                name=name,
                slave_id=i,
                connection="VeterinaTEST",
                requests=[
                    Request("IR", FunctionCode.READ_INPUT_REGISTERS, 515),
                    Request("IR_SetP", FunctionCode.READ_INPUT_REGISTERS, 554),
                    Request("HR", FunctionCode.READ_HOLDING_REGISTERS, 262),
                ],
            )
        )
        mappings.extend(
            [
                ServerMapping(name, name, "IR", 1024 + i, "input_register"),
                ServerMapping(f"{name}_SetP", name, "IR_SetP", 1049 + i, "input_register"),
                ServerMapping(f"HR_{name}", name, "HR", 1079 + i, "holding_register"),
            ]
        )
    return Project(devices=devices, mappings=mappings)


def test_allocator_preserves_request_blocks():
    project = _project()
    assert next_free_register(project, register_type="input_register", request_name="IR") == 1048
    assert next_free_register(project, register_type="input_register", request_name="IR_SetP") == 1073
    assert next_free_register(project, register_type="holding_register", request_name="HR") == 1103


def test_allocator_falls_back_to_register_type():
    project = _project()
    assert next_free_register(project, register_type="input_register", request_name="Unknown") == 1073
