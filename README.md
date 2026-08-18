# Teltonika Modbus Configurator

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments.

The goal is to configure large Modbus installations without manually creating hundreds of entries in the RutOS WebUI or duplicating the same TCP register list in atvise Connect.

A device can be a thermostat, chiller, AHU, meter, pump, VFD, or any other Modbus RTU device.

## v1 scope

The first version focuses on one proven workflow:

```text
Modbus RTU devices
        ↓ RS485
Teltonika TRB / RutOS Modbus Client
        ↓ local value mappings
RutOS Modbus TCP Server
        ↓
atvise Connect (one Modbus TCP connection)
```

Current capabilities:

- Serial Modbus connections and RTU devices
- Arbitrary FC01–FC04 read requests
- RutOS Modbus TCP Server mappings
- Automatic internal UCI IDs and `tag_id` relationships
- Import existing live RutOS Modbus configuration over SSH
- YAML save/load
- Reusable device/request templates
- Bulk device generation with sequential or explicit Slave IDs
- Automatic next-free TCP register allocation
- Collision validation for devices, Slave IDs, symbol names and TCP register ranges
- Exact RutOS UCI preview
- Live unified diff against a TRB
- Guarded SSH apply with local + remote backup
- Remote rollback snapshots
- Windows/Tkinter desktop GUI
- atvise Connect `.Symbol` export for Input Registers and Holding Registers

Modbus TCP Client devices and additional unverified register/symbol types are intentionally deferred to a later version.

## Desktop GUI

Install the project and start it with:

```bash
pip install -e .
tmc-gui
```

The GUI supports:

- New/open/save YAML projects
- Import live TRB configuration over SSH
- Connections editor
- Devices and requests editor
- TCP Server mappings editor
- TCP Server settings
- Bulk Device Generator using any existing device as a template
- Automatic next-free TCP mapping proposals
- Validation
- Generated UCI preview
- Live TRB diff preview
- Guarded Apply requiring explicit `APPLY` confirmation
- Rollback to a saved remote snapshot
- Export of atvise Connect `.Symbol` files

## atvise Connect symbol export

The exporter uses the same TCP mappings that are generated for RutOS, so Connect does not need to be configured manually a second time.

A project containing mappings such as:

```text
Joy01       input_register   1025
Joy01_SetP  input_register   1050
HR_Joy01    holding_register 1080
```

produces:

```text
[]
sym-Joy01=IR1025,
sym-Joy01_SetP=IR1050,
sym-HR_Joy01=HR1080,
```

This matches the tested atvise Connect symbol-file structure supplied during development.

Only enabled mappings are exported by default. v1 supports the verified `IR` and `HR` forms only; unsupported register types fail explicitly instead of guessing Connect syntax.

From the GUI use:

```text
Export → atvise Connect Symbol file...
```

From the CLI:

```bash
tmc export-symbols project.yaml -o Conn-TRB145.Symbol
```

## Import an existing TRB

Read a live configuration over SSH:

```bash
tmc import-live --host 10.33.22.1 -o imported.yaml
```

Or convert previously exported UCI files:

```bash
tmc import-uci modbus_client.txt modbus_server.txt -o imported.yaml
```

The importer resolves RutOS relationships such as:

```text
rtu_server '2'
request_2 '3'
tag_id '2.3'
```

back into explicit project relationships between devices, requests and TCP mappings.

## Bulk generation

The GUI Bulk Device Generator can clone any existing device as a template. For example, a device with three requests can be expanded into a whole line of devices while assigning sequential Slave IDs and separate TCP register blocks.

The generator checks for:

- duplicate device names;
- duplicate Slave IDs on the same serial connection;
- duplicate mapping/symbol names;
- overlapping TCP register ranges.

Loading an existing device template automatically proposes the next free register for each related mapping group.

## CLI

Local operations:

```bash
tmc validate project.yaml
tmc preview project.yaml
tmc export project.yaml -o output
tmc export-symbols project.yaml -o Conn-TRB145.Symbol
```

Compare against a live TRB without writing:

```bash
tmc remote-preview project.yaml --host 10.33.22.1
```

Apply after reviewing the diff:

```bash
tmc apply project.yaml --host 10.33.22.1
```

Rollback:

```bash
tmc rollback <snapshot> --host 10.33.22.1
```

Passwords are prompted interactively and are not stored in YAML. SSH keys are also supported.

## Why UCI?

RutOS stores the live Modbus configuration in packages such as:

- `/etc/config/modbus_client`
- `/etc/config/modbus_server`

A real TRB145 test confirmed that generated UCI sections are accepted by RutOS, appear correctly in the WebUI, and can be linked through the Modbus TCP Server using generated `tag_id` references.

## Safety principle

The configurator does not blindly overwrite a live TRB. Deployment follows:

```text
read live config
    ↓
backup locally + remotely
    ↓
generate and validate
    ↓
show complete diff
    ↓
explicit confirmation
    ↓
apply UCI + commit + restart
    ↓
keep rollback snapshot
```

## Next version

Planned later work includes Modbus TCP Client devices, additional RutOS Modbus options, write-oriented request models, verified Coil/Discrete Input symbol export, reusable device-template libraries and installer/packaging improvements.
