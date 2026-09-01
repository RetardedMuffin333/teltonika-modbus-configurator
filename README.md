# Teltonika Modbus Configurator

> **Unofficial project.** Teltonika Modbus Configurator is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments. It is aimed at larger installations where manually creating hundreds of Modbus requests, TCP Server mappings, and atvise Connect symbols becomes impractical.

## v0.4.0

v0.4 adds a hardware-verified Carel cDesign import workflow, selective SCADA write-target generation, grouped mapping UI, and usability improvements for larger projects while retaining the mixed RTU + TCP aggregation introduced in v0.3.

```text
RTU devices ---- RS485 ----\
                           \
                            Teltonika RutOS
                           / Modbus Client
TCP devices --- Ethernet -/       |
                                  v
                         Modbus TCP Server :502
                                  |
                                  v
                        atvise Connect / SCADA
```

### Current capabilities

- Serial Modbus RTU connections and devices.
- Modbus TCP Client devices alongside RTU devices in the same project/gateway.
- FC01, FC02, FC03, FC04, FC05, FC06, FC15 and FC16.
- Request datatypes including 8/16-bit integers and verified 32-bit INT/UINT/FLOAT byte orders.
- All four Modbus TCP Server areas: Coil, Discrete Input, Holding Register and Input Register.
- Mapping access derived automatically from source request direction: reads -> `r`, writes -> `w`.
- Width-aware allocation and collision detection for 32-bit values.
- Live RutOS import over SSH with source-UCI provenance retained.
- Exact no-op round trip for imported configurations.
- YAML save/load, UCI preview, live diff, guarded deployment, backups and rollback snapshots.
- Bulk Device Generator for RTU and TCP clients.
- First-fit mapping allocation with separate read/write blocks.
- atvise Connect `.Symbol` export.
- Carel cDesign legacy `.xls` import with selective/filterable row import.
- Carel variable-name sanitizing: `.` -> `_`, `[` and `]` removed.
- Optional Carel `Index + 1` conversion for device-specific zero-based addressing.
- Compact TCP Server allocation per Modbus address space after selective Carel import.
- Grouped/collapsible TCP Server Mappings view by source device.
- Double-click Edit on requests and mappings.
- Ctrl/Shift multi-select Delete for requests and mappings.
- Multi-select SCADA write-target creation so only genuine commands/setpoints are exposed as writable.

## Installation

Python 3.11 or newer is required.

```powershell
git clone https://github.com/RetardedMuffin333/teltonika-modbus-configurator.git
cd teltonika-modbus-configurator
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

To update an existing checkout:

```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

## Desktop workflow

The main tabs follow the data path:

```text
1. Modbus Serial Clients
2. Devices & Requests
3. Modbus TCP Clients
4. TCP Server
5. TCP Server Mappings
```

Typical project flow:

```text
create/import client devices
        ↓
create/import requests
        ↓
create TCP Server mappings
        ↓
select actual commands/setpoints for SCADA write targets
        ↓
validate
        ↓
preview UCI / live diff
        ↓
deploy to RutOS
        ↓
export atvise symbols
```

## Mixed RTU + TCP aggregation

A hardware-tested setup is:

```text
Siemens RDF400MB thermostat -- Modbus RTU --\
                                              RUT956
Carel controller ----------- Modbus TCP -----/   |
                                                  v
                                      TCP Server Device ID 101
                                                  |
                                                  v
                                           atvise Connect
```

SCADA can therefore use a single Teltonika Modbus TCP connection while the gateway polls both RTU and TCP source devices.

## Carel cDesign import

v0.4 can read the native legacy `.xls` documentation export produced by Carel cDesign.

Open:

```text
Carel
└── Carel cDesign XLS import...
```

The importer detects columns such as:

```text
Types | Index | Size | Variable Name | DataType | Direction
```

The important fields are interpreted as:

```text
Types      -> Modbus area
Index      -> Carel source register/index
Size       -> value/register width metadata
DataType   -> Carel value datatype
Direction  -> export direction metadata
```

Supported conversions currently include common Carel types such as `Bool`, `USInt`, `SInt`, `UInt`, `Int`, `UDInt`, `DInt` and `Real/FLOAT32`. Unsupported types are skipped rather than guessed.

Imported names are sanitized for RutOS/SCADA use:

```text
Klimati.Scheduler_1.Event_Msk[1].Enabled
→ Klimati_Scheduler_1_Event_Msk1_Enabled
```

### Carel register numbering

Carel projects may use zero-based register numbering. The importer therefore exposes an explicit:

```text
Carel Index + 1 for RutOS request address
```

option. This is device/profile-specific and is not applied globally to every Modbus device.

### Selective import and compact server blocks

Carel source indexes may be sparse, but TCP Server mappings are compacted independently per Modbus address space. This avoids atvise Connect block reads across unmapped gaps.

For example sparse Carel coils can become:

```text
Carel Coil 110 -> TCP Coil 1025
Carel Coil 150 -> TCP Coil 1026
Carel Coil 151 -> TCP Coil 1027
Carel Coil 159 -> TCP Coil 1028
```

while the source requests still point to the correct Carel addresses.

## SCADA command / feedback workflow

RutOS derives TCP Server mapping permission from the source Modbus Client request. Read requests become Read-Only mappings and write requests become Write-Only mappings.

The project therefore uses separate feedback and command paths.

### Hardware-verified write patterns

```text
BOOL / Coil
FC01 enabled feedback
FC05 disabled command

16-bit Holding Register
FC03 enabled feedback
FC06 disabled command

32-bit / FLOAT32 Holding Register
FC03 enabled feedback
FC16 disabled command
```

The write request is intentionally **disabled**. If enabled, RutOS can periodically transmit its configured placeholder value. With the request disabled, the write-only TCP Server mapping is still available for incoming SCADA writes.

### Deliberate write-target selection

Carel `Direction=ReadWrite` is treated as metadata only. It does **not** automatically mean the variable should be writable from SCADA. A sensor may still be located in a Holding Register.

Recommended workflow:

```text
import Carel variables as read paths
        ↓
inspect the imported requests
        ↓
Ctrl/Shift-select only real commands/setpoints
        ↓
SCADA → Create write target from selected TCP request
        ↓
disabled FC05 / FC06 / FC16 companion created
```

New automatic command mappings are kept in a separate high address area (`20000+`) to stay away from normal read polling. Existing v0.3 projects using `HR1200+` remain supported.

## TCP Server Mappings UI

Large projects can contain hundreds of mappings. v0.4 groups mappings by source device:

```text
▶ RDF_Test (12 mappings)
▶ Carel_Test (108 mappings)
▶ RDF_Test_02 (12 mappings)
```

Each group can be expanded or collapsed. Individual mappings remain editable/deletable, while group rows are organizational only.

## Bulk Generator

The Bulk Generator can clone RTU or TCP-client templates, including requests and TCP Server mappings.

It supports sequential/explicit IDs, datatype-aware widths, first-fit allocation, independent Modbus address spaces, template-relative offsets, and separate read/write mapping blocks.

## 32-bit request datatypes

Verified RutOS request tokens include:

```text
FLOAT32
32bit_float1234
32bit_float2143
32bit_float3412
32bit_float4321

INT32
32bit_int1234
32bit_int2143
32bit_int3412
32bit_int4321

UINT32
32bit_uint1234
32bit_uint2143
32bit_uint3412
32bit_uint4321
```

A single FLOAT32 value uses RutOS request `reg_count=1`, while its TCP Server mapping occupies two 16-bit Modbus addresses for allocation/collision purposes.

## atvise Connect symbol export

Verified prefixes currently include:

```text
IR   integer Input Register
HR   integer Holding Register
DI   Discrete Input
DA   Coil / digital output
IRR  FLOAT32 Input Register
HRR  FLOAT32 Holding Register
HRD  FLOAT64 Holding Register
```

From the GUI:

```text
Export
├── atvise Connect Symbol file (all mappings)...
└── atvise Connect Symbol file (enabled only)...
```

## Import and deployment safety

Recommended live workflow:

```text
Import live RutOS
      ↓
Save YAML
      ↓
Validate
      ↓
Edit / import / bulk generate
      ↓
Preview live diff
      ↓
Verify intended changes only
      ↓
Apply
      ↓
Fresh import and compare
```

Passwords are prompted interactively and are not stored in YAML. Do not commit site-specific UCI exports, backups, passwords, private keys or production project files to the public repository.

## CLI

```bash
tmc validate project.yaml
tmc preview project.yaml
tmc export project.yaml -o output
tmc export-symbols project.yaml -o Conn-Teltonika.Symbol
tmc import-live --host <DEVICE-IP> -o imported.yaml
tmc remote-preview project.yaml --host <DEVICE-IP>
tmc apply project.yaml --host <DEVICE-IP>
tmc rollback <snapshot> --host <DEVICE-IP>
```

## Hardware validation history

### v0.1.0

Validated on a real TRB145 running RutOS 7.24.2 using a generated 23-device RTU project.

### v0.2.0

Added write-request generation and safe editing of imported live UCI.

### v0.3.0

Validated mixed RTU + Modbus TCP aggregation, Carel FLOAT32 reads, and the FC03 + disabled FC06 thermostat command/feedback workflow through atvise Connect.

### v0.4.0

Validated on a real RUT956 with Siemens RDF400MB over RS485, Carel controller over Modbus TCP, and atvise Connect as the upstream SCADA client.

Hardware-verified behavior includes:

- native Carel cDesign `.xls` import into TCP-client requests and TCP Server mappings;
- Carel `Index + 1` addressing for the tested controller/project;
- BOOL/Coil reads through FC01;
- 16-bit Holding Register reads through FC03;
- FLOAT32 Holding Register reads through FC03;
- SCADA Coil writes through disabled FC05 companions;
- SCADA 16-bit Holding Register writes through disabled FC06 companions;
- SCADA FLOAT32 writes through disabled FC16 companions;
- feedback reads confirming the written values;
- compact server-side mapping allocation preventing atvise block-read failures;
- grouped mapping UI and multi-select request/mapping workflows on a larger imported project.

## Known limitations / next work

- No standalone Windows installer yet; installation uses Python/pip.
- 64-bit request datatype generation remains deferred until exact RutOS request tokens are verified.
- Some atvise symbol datatype forms remain intentionally rejected rather than guessed.
- Carel import currently targets legacy `.xls`; broader XLSX/CSV support can be added later.
- Carel `Direction` metadata is not treated as authorization to expose a SCADA write path; writable targets are selected deliberately.

See `CHANGELOG.md` for release history.
