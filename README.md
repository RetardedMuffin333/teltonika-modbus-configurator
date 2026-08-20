# Teltonika Modbus Configurator

> **Unofficial project.** Teltonika Modbus Configurator is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments.

The goal is to configure large Modbus installations without manually creating hundreds of entries in the RutOS WebUI or duplicating the same TCP register list in atvise Connect.

A device can be a thermostat, chiller, AHU, meter, pump, VFD, or any other Modbus RTU device.

## v0.2.0

v0.2 expands the proven v0.1 RTU workflow with write requests, writable TCP mappings, richer datatypes, and full editing of imported live configurations while retaining stable RutOS UCI identities.

```text
Modbus RTU devices
        ↕ RS485
Teltonika TRB / RutOS Modbus Client
        ↕
RutOS Modbus TCP Server
        ↕
atvise Connect / other Modbus TCP client
```

### Current capabilities

- Serial Modbus RTU connections and devices
- FC01 Read coils
- FC02 Read discrete inputs
- FC03 Read holding registers
- FC04 Read input registers
- FC05 Set single coil
- FC06 Set single holding register
- FC15 Set multiple coils
- FC16 Set multiple holding registers
- Separate read-count and write-value semantics
- Request datatypes currently generated from scratch for:
  - 8-bit INT / UINT
  - 16-bit INT / UINT, high-byte-first or low-byte-first
  - Bool, ASCII, Hex and PDU where supported by RutOS
- Lossless preservation of imported RutOS datatype tokens not yet decoded by the configurator
- All four Modbus TCP Server areas: Coil, Discrete Input, Holding Register, Input Register
- TCP mapping permissions: Read-Only, Write-Only, Read-Write
- TCP mapping datatypes including Binary, String, Bool, integer widths and FLOAT32/FLOAT64 metadata
- Automatic internal UCI IDs and `tag_id` relationships
- Import existing live RutOS Modbus configuration over SSH
- Exact no-op round trip: import → no edits → byte-for-byte original UCI
- Edit, rename, add and delete imported connections, devices, requests and TCP mappings
- Edit imported TCP Server settings
- Stable provenance IDs for imported RutOS sections, avoiding unrelated ID renumbering
- YAML save/load including imported UCI provenance IDs
- Reusable device/request templates
- Bulk device generation with sequential or explicit/non-sequential Slave IDs
- Bulk support for read and write requests
- Automatic next-free TCP register allocation
- Teltonika TCP register validation: `1025..65536`
- Validation of function code vs Modbus register area and read/write permissions
- Collision validation for devices, Slave IDs, symbol names and TCP register ranges
- Exact RutOS UCI preview
- Live unified diff against a TRB
- Guarded SSH apply with local + remote backup
- Remote rollback snapshots
- Windows/Tkinter desktop GUI
- atvise Connect `.Symbol` export for verified Input Register (`IR`) and Holding Register (`HR`) mappings

### Known v0.2 limitations

- Modbus TCP Client devices are not modeled yet.
- Fresh generation of all 32/64-bit request byte-order variants is intentionally deferred until their exact RutOS UCI tokens are verified on hardware. Imported unknown tokens are preserved losslessly.
- atvise `.Symbol` export is still intentionally limited to verified `IR` and `HR` forms. Coil/Discrete Input and float/double symbol forms will be added after verification.
- No standalone Windows installer yet; installation uses Python/pip.

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
- Read and write request creation
- Read-Only / Write-Only / Read-Write TCP mappings
- Bulk Device Generator using any existing device as a template
- Sequential or explicit/non-sequential Slave IDs
- Automatic next-free TCP mapping proposals
- Validation
- Generated UCI preview
- Live TRB diff preview
- Guarded Apply requiring explicit `APPLY` confirmation
- Rollback to a saved remote snapshot
- Export of atvise Connect `.Symbol` files

## Read/write command-feedback pattern

v0.2 supports the common pattern where one physical holding register is written through one request and independently polled through another:

```text
SCADA writes TCP HR1032
        ↓
CMD_WorkMode
FC06 / physical HR101
Enabled = OFF

physical HR101
        ↓
Status_CMD_WorkMode
FC03 / physical HR101
Enabled = ON
        ↓
SCADA reads TCP HR1035
```

This keeps command and feedback as separate SCADA addresses while both point to the same physical device register.

## Recommended live workflow

For an existing TRB:

```text
Import live TRB
      ↓
Save YAML
      ↓
Validate
      ↓
Add / edit / delete configuration
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

A successful final verification should report no difference between the fresh live import and generated configuration.

### Round-trip safety

Imported projects preserve the original `modbus_client` and `modbus_server` UCI plus stable source IDs for imported entities. With no edits, generation returns the original UCI byte-for-byte.

When an imported entity is edited, v0.2 updates the section with its existing UCI ID rather than reconstructing unrelated sections. Newly added sections receive deterministic IDs above the existing range. Unknown RutOS options in edited sections are retained where possible.

## Bulk generation

The Bulk Device Generator can clone any existing device as a template, including multiple requests and TCP mappings.

The generator supports sequential and explicit/non-sequential Slave IDs and validates:

- duplicate device names;
- duplicate Slave IDs on the same serial connection;
- duplicate mapping/symbol names;
- overlapping TCP register ranges;
- TCP registers outside `1025..65536`;
- invalid function/register-area combinations;
- invalid read/write mapping permissions.

## atvise Connect symbol export

The exporter uses the same TCP mappings generated for RutOS so the register list does not need to be entered manually a second time.

Example:

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

From the GUI:

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

Or convert exported UCI files:

```bash
tmc import-uci modbus_client.txt modbus_server.txt -o imported.yaml
```

The importer resolves relationships such as:

```text
rtu_server '2'
request_2 '13'
tag_id '2.13'
```

into explicit project relationships while retaining those source IDs for later edits.

## CLI

```bash
tmc validate project.yaml
tmc preview project.yaml
tmc export project.yaml -o output
tmc export-symbols project.yaml -o Conn-TRB145.Symbol
tmc remote-preview project.yaml --host <TRB-IP>
tmc apply project.yaml --host <TRB-IP>
tmc rollback <snapshot> --host <TRB-IP>
```

Passwords are prompted interactively and are not stored in YAML. SSH keys are also supported.

## Deployment safety

The configurator does not blindly overwrite a live TRB:

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

Always review the live diff before applying changes.

## Hardware validation history

### v0.1.0 baseline

v0.1.0 was validated on a real Teltonika TRB145 running RutOS 7.24.2 with a fresh generated batch of 23 RTU devices, three requests per device, and corresponding TCP mappings. RutOS accepted the generated UCI and the configuration worked live.

### v0.2.0

v0.2 retains the v0.1 baseline and adds generated read/write request support and stable editing of imported live UCI. Release-candidate validation includes clean generated diffs for FC06 Write-Only command mappings and FC03 Read-Only feedback mappings targeting the same physical holding register. Final hardware acceptance should be completed before the release branch is frozen.

## Security and public-repository notes

- Do not commit exported live UCI files, device backups, site-specific project YAML files, SSH private keys, passwords, or other credentials.
- Review the live diff before every deployment.
- Prefer test devices or disabled entries for first-time deployment checks.
- This project modifies live device configuration over SSH; use it only on equipment you are authorized to administer.

## Planned next work

- Modbus TCP Client devices alongside RTU devices
- complete verified 32/64-bit request datatype and byte-order generation
- verified atvise `DI`, `DA`, `IRR`, `HRR`, `HRD` and related symbol forms
- reusable device-template libraries/catalogs
- richer bulk editing
- object-level live diff summaries
- dependency-aware delete helpers
- installer/packaging improvements

See `CHANGELOG.md` for release history.
