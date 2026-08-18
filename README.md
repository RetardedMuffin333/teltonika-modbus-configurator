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
- SSH live preview / apply / rollback
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

## CLI

Validate and preview locally:

```bash
tmc validate examples/bulk_devices.yaml
tmc preview examples/bulk_devices.yaml
tmc export examples/bulk_devices.yaml -o output
```

Compare a generated project with the live TRB without writing anything:

```bash
tmc remote-preview examples/bulk_devices.yaml --host 10.33.22.1
```

Apply only after reviewing the diff:

```bash
tmc apply examples/bulk_devices.yaml --host 10.33.22.1
```

`apply` performs the safety sequence automatically:

1. reads the live `modbus_client` and `modbus_server` UCI exports;
2. prints a unified diff;
3. requires explicit confirmation;
4. stores a local backup under `backups/<UTC timestamp>/`;
5. creates a remote snapshot under `/root/tmc-backups/<UTC timestamp>/`;
6. imports and validates the generated UCI before commit;
7. commits and restarts the Modbus services.

Rollback a snapshot with:

```bash
tmc rollback 20260818T090000Z --host 10.33.22.1
```

SSH passwords are prompted interactively and are not stored in project YAML. SSH keys can be supplied with `--key`. Unknown host keys are rejected unless `--trust-new-host` is explicitly supplied.

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

- [x] SSH connection
- [x] Read live UCI configuration
- [x] Backup current Modbus config
- [x] Diff / preview
- [x] Apply configuration
- [x] Restart affected services
- [x] Rollback

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

The configurator should never blindly overwrite a live TRB configuration. Deployment follows:

1. Read live configuration.
2. Back it up locally and remotely.
3. Generate proposed configuration.
4. Validate references and address conflicts.
5. Show a diff/preview.
6. Apply only after explicit confirmation.
7. Keep a rollback snapshot.

## Status

Early development. The first successful proof-of-concept generated a disabled RTU device and a linked Modbus TCP Server mapping and applied both to a TRB145 via UCI. The project now supports reusable templates, bulk device groups, and a guarded SSH deployment workflow.
