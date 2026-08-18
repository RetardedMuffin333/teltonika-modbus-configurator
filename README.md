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
- Tkinter desktop editor for YAML/live projects, connections, devices, requests, mappings, TCP Server settings, validation and UCI preview

## Desktop GUI

The first desktop UI is deliberately a thin layer over the tested core. It does not maintain a separate configuration format; edits are made directly to the same `Project` model used by the CLI.

Install the project and start it with:

```bash
pip install -e .
tmc-gui
```

The GUI currently supports:

- new/open/save YAML projects;
- import the live `modbus_client` and `modbus_server` configuration from a TRB over SSH;
- add/edit/delete serial connections;
- add/edit/delete devices and their Modbus requests;
- add/edit/delete Modbus TCP Server mappings;
- edit TCP Server port, Device ID, enabled state and persistent connection;
- validate the project;
- preview the exact generated RutOS UCI before any deployment.

Live **apply/rollback from the GUI is intentionally not enabled yet**. The CLI remains the guarded deployment path until the GUI has a proper diff/confirmation/backup workflow.

## Why UCI?

RutOS stores the live Modbus configuration in packages such as:

- `/etc/config/modbus_client`
- `/etc/config/modbus_server`

A working TRB145 test confirmed that generated UCI sections are accepted by RutOS and appear correctly in the WebUI.

## Import an existing TRB

The configurator can start from an already-configured device instead of requiring a handwritten YAML project.

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

- [x] Windows desktop application foundation
- [x] Open live TRB / YAML project
- [x] Connections editor
- [x] Devices editor
- [x] Requests editor
- [x] TCP mapping editor
- [x] Validation / UCI preview
- [ ] GUI diff / guarded Apply / Rollback workflow
- [ ] Bulk/template editor UI

### Phase 5 — Additional transports / writes

- [ ] Modbus TCP Client devices
- [ ] Write-oriented request/mapping model
- [ ] Preserve and edit additional RutOS Modbus options

## Safety principle

The configurator should never blindly overwrite a live TRB configuration. Deployment follows: read live config → back up → generate → validate → diff → explicit confirmation → apply → keep rollback snapshot.

## Status

The CLI can round-trip between a live RutOS Modbus configuration and the generic YAML project model. A first desktop editor now sits on top of that same core. The next GUI milestone is guarded live diff/apply/rollback; Modbus TCP Client support will be added once a populated real RutOS TCP-client UCI example is available.
