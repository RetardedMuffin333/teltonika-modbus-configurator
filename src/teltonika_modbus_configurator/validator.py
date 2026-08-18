"""Project validation before UCI generation or deployment."""

from dataclasses import dataclass

from .models import Project


TELTONIKA_TCP_REGISTER_MIN = 1025
TELTONIKA_TCP_REGISTER_MAX = 65536


@dataclass(slots=True)
class ValidationMessage:
    level: str
    message: str


def validate_project(project: Project) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    connection_names = [c.name for c in project.connections]
    if len(connection_names) != len(set(connection_names)):
        messages.append(ValidationMessage("error", "Duplicate connection names"))

    device_names = [d.name for d in project.devices]
    if len(device_names) != len(set(device_names)):
        messages.append(ValidationMessage("error", "Duplicate device names"))

    for device in project.devices:
        if device.connection not in connection_names:
            messages.append(
                ValidationMessage(
                    "error", f"{device.name}: unknown connection '{device.connection}'"
                )
            )
        if not 1 <= device.slave_id <= 247:
            messages.append(
                ValidationMessage("error", f"{device.name}: slave_id must be 1..247")
            )

        request_names = [r.name for r in device.requests]
        if len(request_names) != len(set(request_names)):
            messages.append(
                ValidationMessage("error", f"{device.name}: duplicate request names")
            )

        for request in device.requests:
            if request.register < 0:
                messages.append(
                    ValidationMessage(
                        "error", f"{device.name}/{request.name}: register cannot be negative"
                    )
                )
            if request.count < 1:
                messages.append(
                    ValidationMessage(
                        "error", f"{device.name}/{request.name}: count must be at least 1"
                    )
                )

    # Duplicate slave IDs are only an error when devices share the same connection.
    seen_slave: set[tuple[str, int]] = set()
    for device in project.devices:
        key = (device.connection, device.slave_id)
        if key in seen_slave:
            messages.append(
                ValidationMessage(
                    "error",
                    f"Duplicate slave ID {device.slave_id} on connection {device.connection}",
                )
            )
        seen_slave.add(key)

    devices = {d.name: d for d in project.devices}
    seen_mapping_address: set[tuple[str, int]] = set()
    for mapping in project.mappings:
        device = devices.get(mapping.device)
        if device is None:
            messages.append(
                ValidationMessage(
                    "error", f"{mapping.name}: unknown device '{mapping.device}'"
                )
            )
            continue

        if mapping.request not in {r.name for r in device.requests}:
            messages.append(
                ValidationMessage(
                    "error",
                    f"{mapping.name}: unknown request '{mapping.request}' on {mapping.device}",
                )
            )

        if not TELTONIKA_TCP_REGISTER_MIN <= mapping.register <= TELTONIKA_TCP_REGISTER_MAX:
            messages.append(
                ValidationMessage(
                    "error",
                    f"{mapping.name}: TCP register must be "
                    f"{TELTONIKA_TCP_REGISTER_MIN}..{TELTONIKA_TCP_REGISTER_MAX}",
                )
            )

        key = (mapping.register_type, mapping.register)
        if key in seen_mapping_address:
            messages.append(
                ValidationMessage(
                    "error",
                    f"Duplicate TCP mapping {mapping.register_type} {mapping.register}",
                )
            )
        seen_mapping_address.add(key)

    return messages


def raise_for_errors(messages: list[ValidationMessage]) -> None:
    errors = [m.message for m in messages if m.level == "error"]
    if errors:
        raise ValueError("Validation failed:\n- " + "\n- ".join(errors))
