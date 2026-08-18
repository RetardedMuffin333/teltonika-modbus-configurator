# Teltonika Modbus Configurator

A configuration tool for Teltonika RutOS Modbus deployments.

The goal is to make large Modbus configurations manageable without manually creating hundreds of entries in the RutOS WebUI.

## Scope

The project is intentionally **device-agnostic**. A configured device can be a thermostat, chiller, AHU, meter, pump, VFD, or any other Modbus device.

The core model supports:

- Serial Modbus connections
- Modbus RTU devices
- Modbus requests
- RutOS Modbus TCP Server mappings
- Internal `tag_id` relationship generation
- Validation before deployment
- UCI export generation
- Reusable device/request templates
- Bulk device generation
- Later: SSH apply, backup and rollback
- Later: Modbus TCP Client devices
- Later: Windows GUI

## Why UCI?

RutOS stores the live Modbus configuration in UCI packages such as:

- `/etc/config/modbus_client`
- `/etc/config/modbus_server`

A working test confirmed that generated UCI sections can be imported into a TRB145 and are then recognized correctly by the RutOS WebUI.

## Bulk templates

Repeated devices do not need to be written out individually. Define a template once and instantiate it with a `device_group`.

```yaml
connections:
  - name: RS485_Main
    type: serial
    baudrate: 19200
    databits: 8
    parity: none
    stopbits: 2

templates:
  room_controller:
    requests:
      - name: Temperature
        function: 4
        register: 515
      - name: SetpointStatus
        function: 4
        register: 554
      - name: SetpointCommand
        function: 3
        register: 262

    mappings:
      - name: "{device}_Temp"
        request: Temperature
        register_type: input_register
        start_register: 1025
      - name: "{device}_SetP"
        request: SetpointStatus
        register_type: input_register
        start_register: 1050
      - name: "HR_{device}"
        request: SetpointCommand
        register_type: holding_register
        start_register: 1080

device_groups:
  - template: room_controller
    connection: RS485_Main
    name_pattern: "Room{index:02d}"
    count: 20
    slave_start: 1
```

This expands to `Room01` through `Room20`, Slave IDs 1 through 20, with sequential TCP mappings starting at the configured register ranges.

For installations with non-sequential addresses, `slave_ids` can be supplied explicitly:

```yaml
device_groups:
  - template: room_controller
    connection: RS485_Main
    name_pattern: "Device{index:02d}"
    count: 4
    slave_ids: [1, 44, 47, 97]
```

## Development plan

### Phase 1 — Core

- [x] Define repository structure
- [x] YAML project model
- [ ] UCI parser
- [x] UCI generator
- [x] `tag_id` relationship generation
- [x] Validation
- [x] CLI preview/export
- [x] Unit tests

### Phase 2 — Deployment

- [ ] SSH connection
- [ ] Read live UCI configuration
- [ ] Backup current Modbus config
- [ ] Diff / preview
- [ ] Apply configuration
- [ ] Restart affected services
- [ ] Rollback

### Phase 3 — Device templates

- [x] Reusable request templates
- [x] Bulk device generation
- [x] Sequential Slave ID generation
- [x] Sequential TCP register allocation
- [ ] Template library for common devices

### Phase 4 — GUI

- [ ] Windows desktop application
- [ ] Connections editor
- [ ] Devices editor
- [ ] Requests editor
- [ ] TCP mapping editor
- [ ] Validation panel
- [ ] Preview / Apply / Rollback workflow

## Safety principle

The configurator should never blindly overwrite a live TRB configuration. Deployment should follow:

1. Read live configuration.
2. Back it up.
3. Generate proposed configuration.
4. Validate references and address conflicts.
5. Show a diff/preview.
6. Apply only after explicit confirmation.
7. Keep a rollback copy.

## Status

Early development. The first successful proof-of-concept generated a disabled RTU device and a linked Modbus TCP Server mapping and applied both to a TRB145 via UCI. The generator now also supports reusable templates and bulk device groups.
