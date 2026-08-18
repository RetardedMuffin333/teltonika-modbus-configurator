# Teltonika Modbus Configurator

> **Unofficial project.** Teltonika Modbus Configurator is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments.

The goal is to configure large Modbus installations without manually creating hundreds of entries in the RutOS WebUI or duplicating the same TCP register list in atvise Connect.

A device can be a thermostat, chiller, AHU, meter, pump, VFD, or any other Modbus RTU device.

## v0.1.0 — proven baseline

Version `0.1.0` freezes the first end-to-end workflow that was successfully tested on a real Teltonika TRB145 running RutOS 7.24.2:

```text
Modbus RTU devices
        ↓ RS485
Teltonika TRB145 / RutOS Modbus Client
        ↓ local value mappings
RutOS Modbus TCP Server
        ↓
atvise Connect (one Modbus TCP connection)
```

The release acceptance test generated and deployed a fresh batch of 23 Modbus RTU devices, each with three requests, plus the corresponding Modbus TCP Server mappings. RutOS accepted the generated UCI, the entries appeared correctly in the WebUI, polling worked, and the resulting values were exposed through the single Modbus TCP Server connection.

### Current capabilities

- Serial Modbus connections and RTU devices
- Arbitrary FC01–FC04 read requests
- RutOS Modbus TCP Server mappings
- Automatic internal UCI IDs and `tag_id` relationships
- Import existing live RutOS Modbus configuration over SSH
- Exact no-op round-trip for live imports: import → no edits → zero diff
- Safe append-only generation for imported live projects
- YAML save/load, including imported UCI provenance
- Reusable device/request templates
- Bulk device generation with sequential or explicit Slave IDs
- Automatic next-free TCP register allocation
- Teltonika TCP register validation: `1025..65536`
- Collision validation for devices, Slave IDs, symbol names and TCP register ranges
- Exact RutOS UCI preview
- Live unified diff against a TRB
- Guarded SSH apply with local + remote backup
- Remote rollback snapshots
- Windows/Tkinter desktop GUI
- atvise Connect `.Symbol` export for Input Registers and Holding Registers

Modbus TCP Client devices and additional unverified register/symbol types are intentionally deferred to a later version.

## Installation

Python 3.11 or newer is required. Git is useful for cloning/updating the project.

On Windows:

```powershell
git clone https://github.com/RetardedMuffin333/teltonika-modbus-configurator.git
cd teltonika-modbus-configurator
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

PowerShell activation is optional; the commands above work even when `Activate.ps1` is blocked by execution policy.

To update an existing checkout:

```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -e .
```

## Desktop GUI

The GUI supports:

- New/open/save YAML projects
- Import live TRB configuration over SSH
- Connections editor
- Devices and requests editor
- TCP Server mappings editor
- TCP Server settings
- Bulk Device Generator using any existing device as a template
- Sequential or explicit/non-sequential Slave IDs
- Automatic next-free TCP mapping proposals
- Validation
- Generated UCI preview
- Live TRB diff preview
- Guarded Apply requiring explicit `APPLY` confirmation
- Rollback to a saved remote snapshot
- Export of atvise Connect `.Symbol` files

## Recommended live workflow

For an existing TRB, use this sequence:

```text
Import live TRB
      ↓
Validate
      ↓
Make additions in the GUI / Bulk Generator
      ↓
Preview live diff
      ↓
Verify only intended changes are present
      ↓
Apply to live TRB
      ↓
Fresh import
      ↓
Preview live diff again
```

For a successful deployment, the final fresh import should report that the live configuration already matches the generated configuration.

### Round-trip safety

Imported projects preserve the original `modbus_client` and `modbus_server` UCI as provenance. With no edits, generation returns the original configuration exactly, preventing accidental UCI ID renumbering or broken `tag_id` references.

For v0.1.0, imported projects are intentionally append-only: existing imported connections, devices, requests, mappings and TCP Server settings are protected from silent reconstruction. New entries receive IDs above the existing UCI range.

## Bulk generation

The Bulk Device Generator can clone any existing device as a template. A template may contain multiple requests and multiple TCP mappings.

The generator supports both simple sequential Slave IDs and real-world non-sequential address lists. It checks for:

- duplicate device names;
- duplicate Slave IDs on the same serial connection;
- duplicate mapping/symbol names;
- overlapping TCP register ranges;
- TCP registers outside the Teltonika-supported `1025..65536` range.

Loading an existing device template automatically proposes the next free register for each related mapping group.

## atvise Connect symbol export

The exporter uses the same TCP mappings generated for RutOS, so Connect does not need to be configured manually a second time.

A project containing mappings such as:

```text
Joy01_Temp   input_register   1025
Joy01_SetP   input_register   1050
Joy01_OnOff  holding_register 1080
```

produces:

```text
[]
sym-Joy01_Temp=IR1025,
sym-Joy01_SetP=IR1050,
sym-Joy01_OnOff=HR1080,
```

The normal GUI export includes all mappings, including disabled mappings. A separate enabled-only export is available when a runtime-only symbol list is preferred.

v0.1.0 supports the verified `IR` and `HR` forms only; unsupported register types fail explicitly instead of guessing Connect syntax.

From the GUI use:

```text
Export
├── atvise Connect Symbol file (all mappings)...
└── atvise Connect Symbol file (enabled only)...
```

From the CLI:

```bash
tmc export-symbols project.yaml -o Conn-TRB145.Symbol
```

## Import an existing TRB

Read a live configuration over SSH:

```bash
tmc import-live --host <TRB-IP> -o imported.yaml
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
tmc remote-preview project.yaml --host <TRB-IP>
```

Apply after reviewing the diff:

```bash
tmc apply project.yaml --host <TRB-IP>
```

Rollback:

```bash
tmc rollback <snapshot> --host <TRB-IP>
```

Passwords are prompted interactively and are not stored in YAML. SSH keys are also supported.

## RutOS UCI

RutOS stores the Modbus configuration in packages such as:

```text
/etc/config/modbus_client
/etc/config/modbus_server
```

The configurator generates the UCI relationships used by RutOS, including references between Modbus Client requests and Modbus TCP Server tags.

## Deployment safety

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

Always review the live diff before applying a fresh project that is intended to replace an existing configuration.

## Tested v0.1.0 scenario

The release was validated with a real 23-device RTU batch using a mixture of sequential and non-sequential Slave IDs. Each device contained three read requests:

```text
Temperature  → FC04 / register 515
Setpoint     → FC04 / register 554
On/Off       → FC03 / register 262
```

The TCP Server exposed three separate blocks:

```text
Temperature  → IR1025...
Setpoint     → IR1050...
On/Off       → HR1080...
```

The exact addresses and Device ID are project-specific; the important result is that a completely fresh project generated by the configurator was successfully pushed to the TRB145 and worked live.

## Security and public-repository notes

- Do not commit exported live UCI files, device backups, project YAML files containing site-specific configuration, SSH private keys, passwords, or other credentials.
- Review the live diff before every deployment.
- Prefer test devices or disabled entries for first-time deployment checks.
- This project modifies live device configuration over SSH; use it only on equipment you are authorized to administer.

## Next version

Planned later work includes:

- Modbus TCP Client devices alongside RTU devices
- more RutOS Modbus options and request types
- verified Coil / Discrete Input atvise symbol export
- reusable device-template libraries
- installer / packaging improvements
- broader edit/update support for already-imported live entities

See `CHANGELOG.md` for the frozen v0.1.0 feature set.
