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
- Later: SSH apply, backup and rollback
- Later: Modbus TCP Client devices
- Later: Windows GUI

## Why UCI?

RutOS stores the live Modbus configuration in UCI packages such as:

- `/etc/config/modbus_client`
- `/etc/config/modbus_server`

A working test confirmed that generated UCI sections can be imported into a TRB145 and are then recognized correctly by the RutOS WebUI.

## Development plan

### Phase 1 — Core

- [x] Define repository structure
- [ ] YAML project model
- [ ] UCI parser
- [ ] UCI generator
- [ ] `tag_id` relationship generation
- [ ] Validation
- [ ] CLI preview/export
- [ ] Unit tests

### Phase 2 — Deployment

- [ ] SSH connection
- [ ] Read live UCI configuration
- [ ] Backup current Modbus config
- [ ] Diff / preview
- [ ] Apply configuration
- [ ] Restart affected services
- [ ] Rollback

### Phase 3 — Device templates

- [ ] Reusable request templates
- [ ] Bulk device generation
- [ ] Sequential Slave ID generation
- [ ] Sequential TCP register allocation
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

Early development. The first successful proof-of-concept generated a disabled RTU device and a linked Modbus TCP Server mapping and applied both to a TRB145 via UCI.
