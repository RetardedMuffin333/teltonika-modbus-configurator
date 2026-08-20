"""Project validation before UCI generation or deployment."""

from dataclasses import dataclass

from .models import FunctionCode, Project, permissions_for_function

TELTONIKA_TCP_REGISTER_MIN = 1025
TELTONIKA_TCP_REGISTER_MAX = 65536
REQUEST_DATA_TYPES = {"int8", "uint8", "int16", "uint16", "ascii", "hex", "bool", "pdu", "raw"}
REQUEST_TYPE_ORDERS = {
    "int8": {"none"}, "uint8": {"none"},
    "int16": {"high_byte_first", "low_byte_first"},
    "uint16": {"high_byte_first", "low_byte_first"},
    "ascii": {"none"}, "hex": {"none"}, "bool": {"none"}, "pdu": {"none"}, "raw": {"raw"},
}
TCP_DATA_TYPES = {"binary", "string", "bool", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "float32", "float64"}
FUNCTION_REGISTER_TYPES = {
    FunctionCode.READ_COILS: "coil", FunctionCode.READ_DISCRETE_INPUTS: "discrete_input",
    FunctionCode.READ_HOLDING_REGISTERS: "holding_register", FunctionCode.READ_INPUT_REGISTERS: "input_register",
    FunctionCode.WRITE_SINGLE_COIL: "coil", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER: "holding_register",
    FunctionCode.WRITE_MULTIPLE_COILS: "coil", FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS: "holding_register",
}

@dataclass(slots=True)
class ValidationMessage:
    level: str
    message: str


def validate_project(project: Project) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    connection_names = [c.name for c in project.connections]
    if len(connection_names) != len(set(connection_names)): messages.append(ValidationMessage("error", "Duplicate connection names"))
    device_names = [d.name for d in project.devices]
    if len(device_names) != len(set(device_names)): messages.append(ValidationMessage("error", "Duplicate device names"))

    for device in project.devices:
        if device.connection not in connection_names: messages.append(ValidationMessage("error", f"{device.name}: unknown connection '{device.connection}'"))
        if not 1 <= device.slave_id <= 247: messages.append(ValidationMessage("error", f"{device.name}: slave_id must be 1..247"))
        request_names = [r.name for r in device.requests]
        if len(request_names) != len(set(request_names)): messages.append(ValidationMessage("error", f"{device.name}: duplicate request names"))
        for request in device.requests:
            prefix = f"{device.name}/{request.name}"
            if not 0 <= request.register <= 65535: messages.append(ValidationMessage("error", f"{prefix}: first register must be 0..65535"))
            if request.data_type not in REQUEST_DATA_TYPES:
                messages.append(ValidationMessage("error", f"{prefix}: unsupported request data_type '{request.data_type}'"))
            elif request.byte_order not in REQUEST_TYPE_ORDERS[request.data_type]:
                messages.append(ValidationMessage("error", f"{prefix}: invalid byte order '{request.byte_order}' for {request.data_type}"))
            if request.data_type == "raw" and not request.raw_data_type: messages.append(ValidationMessage("error", f"{prefix}: raw datatype requires raw_data_type"))
            if request.function.is_read:
                if not 1 <= request.count <= 2000: messages.append(ValidationMessage("error", f"{prefix}: read register count must be 1..2000"))
            else:
                if request.values is None or not str(request.values).strip(): messages.append(ValidationMessage("error", f"{prefix}: FC{int(request.function):02d} requires a value/values"))
                elif request.function in {FunctionCode.WRITE_SINGLE_COIL, FunctionCode.WRITE_SINGLE_HOLDING_REGISTER} and len(str(request.values).split()) != 1:
                    messages.append(ValidationMessage("error", f"{prefix}: FC{int(request.function):02d} accepts exactly one value"))
                if request.data_type == "pdu": messages.append(ValidationMessage("error", f"{prefix}: PDU is not a documented write datatype"))

    seen_slave: set[tuple[str, int]] = set()
    for device in project.devices:
        key = (device.connection, device.slave_id)
        if key in seen_slave: messages.append(ValidationMessage("error", f"Duplicate slave ID {device.slave_id} on connection {device.connection}"))
        seen_slave.add(key)

    devices = {d.name: d for d in project.devices}; seen_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for mapping in project.mappings:
        device = devices.get(mapping.device)
        if device is None: messages.append(ValidationMessage("error", f"{mapping.name}: unknown device '{mapping.device}'")); continue
        request = next((r for r in device.requests if r.name == mapping.request), None)
        if request is None: messages.append(ValidationMessage("error", f"{mapping.name}: unknown request '{mapping.request}' on {mapping.device}")); continue
        if mapping.data_type not in TCP_DATA_TYPES: messages.append(ValidationMessage("error", f"{mapping.name}: unsupported TCP data_type '{mapping.data_type}'"))
        if mapping.count < 1: messages.append(ValidationMessage("error", f"{mapping.name}: TCP mapping count must be at least 1"))
        expected_type = FUNCTION_REGISTER_TYPES[request.function]
        if mapping.register_type != expected_type: messages.append(ValidationMessage("error", f"{mapping.name}: {mapping.register_type} does not match FC{int(request.function):02d} source ({expected_type})"))
        expected_access = permissions_for_function(request.function)
        if mapping.permissions != expected_access:
            messages.append(ValidationMessage("error", f"{mapping.name}: access is automatic for FC{int(request.function):02d} and must be '{expected_access}'"))

        end = mapping.register + mapping.count - 1
        if not TELTONIKA_TCP_REGISTER_MIN <= mapping.register <= TELTONIKA_TCP_REGISTER_MAX:
            messages.append(ValidationMessage("error", f"{mapping.name}: TCP register must be {TELTONIKA_TCP_REGISTER_MIN}..{TELTONIKA_TCP_REGISTER_MAX}"))
        elif end > TELTONIKA_TCP_REGISTER_MAX:
            messages.append(ValidationMessage("error", f"{mapping.name}: TCP register range must stay within {TELTONIKA_TCP_REGISTER_MIN}..{TELTONIKA_TCP_REGISTER_MAX}"))
        ranges = seen_ranges.setdefault(mapping.register_type, [])
        for other_start, other_end, other_name in ranges:
            if mapping.register <= other_end and end >= other_start: messages.append(ValidationMessage("error", f"TCP mapping {mapping.name} overlaps {other_name} on {mapping.register_type}"))
        ranges.append((mapping.register, end, mapping.name))
    return messages


def raise_for_errors(messages: list[ValidationMessage]) -> None:
    errors = [m.message for m in messages if m.level == "error"]
    if errors: raise ValueError("Validation failed:\n- " + "\n- ".join(errors))
