# Teltonika Modbus Configurator

A configuration tool for Teltonika RutOS Modbus deployments.

The goal is to make large Modbus configurations manageable without manually creating hundreds of entries in the RutOS WebUI.

The project is intentionally **device-agnostic**: a device can be a thermostat, chiller, AHU, meter, pump, VFD, or any other Modbus device.

## Current capabilities

- Serial Modbus connections and RTU devices
- Arbitrary Modbus read requests
- RutOS Modbus TCP Server mappings
- Automatic internal IDs and `tag_id` relationships
- Reusable request/device templates
- Bulk generation with sequential or explicit Slave IDs
- Sequential TCP register allocation
- YAML validation
- RutOS UCI generation
- Import existing RutOS `modbus_client` / `modbus_server` UCI back to YAML
- Read a live TRB configuration over SSH and convert it to editable YAML
- Remote diff preview
- Guarded SSH apply with local + remote backup
- Rollback to a previous remote snapshot

## Why UCI?

RutOS stores the live Modbus configuration in packages such as:

- `/etc/config/modbus_client`
- `/etc/config/modbus_server`

A working TRB145 test confirmed that generated UCI sections are accepted by RutOS and appear correctly in the WebUI.

## Import an existing TRB

The configurator can now start from an already-configured device instead of requiring a handwritten YAML project.

Read the live configuration over SSH:

```bash
tmc import-live --host 10.33.22.1 -o imported.yaml
```

Or convert previously exported UCI files:

```bash
tmc import-uci modbus_client.txt modbus_server.txt -o imported.yaml
```

The importer resolves RutOS internal relationships such as:

```text
rtu_server '2'
request_2 '3'
tag_id '2.3'
```

back into explicit project relationships:

```yaml
device: TEST01
request: IR_TEST
```

TCP Server settings such as port and Device ID are also preserved in the project model.

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

tcp_server:
  port: 502
  device_id: 101

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

For non-sequential addresses, use an explicit list:

```yaml
device_groups:
  - template: room_controller
    connection: RS485_Main
    name_pattern: "Device{index:02d}"
    count: 4
    slave_ids: [1, 44, 47, 97]
```

## CLI

Local operations:

```bash
tmc validate project.yaml
tmc preview project.yaml
tmc export project.yaml -o output
```

Compare against a live TRB without writing anything:

```bash
tmc remote-preview project.yaml --host 10.33.22.1
```

Apply after reviewing the diff:

```bash
tmc apply project.yaml --host 10.33.22.1
```

`apply` reads the live configuration, prints a unified diff, asks for explicit confirmation, creates local and remote backups, imports and validates the generated UCI, commits it, and restarts the Modbus services.

Rollback:

```bash
tmc rollback 20260818T090000Z --host 10.33.22.1
```

SSH passwords are prompted interactively and are not stored in YAML. SSH keys can be supplied with `--key`. Unknown host keys are rejected unless `--trust-new-host` is explicitly supplied.

## Development plan

### Phase 1 — Core

- [x] YAML project model
- [x] UCI parser/importer
- [x] UCI generator
- [x] `tag_id` relationship generation
- [x] Validation
- [x] CLI preview/export/import
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
- [ ] Open live TRB / YAML project
- [ ] Connections editor
- [ ] Devices editor
- [ ] Requests editor
- [ ] TCP mapping editor
- [ ] Validation panel
- [ ] Preview / Apply / Rollback workflow

## Safety principle

The configurator should never blindly overwrite a live TRB configuration. Deployment follows: read live config → back up → generate → validate → diff → explicit confirmation → apply → keep rollback snapshot.

## Status

The CLI can now round-trip between a live RutOS Modbus configuration and the generic YAML project model. The next major milestone is a GUI on top of this core, plus support for additional Modbus connection types and write-oriented workflows.
