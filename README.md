# Teltonika Modbus Configurator

> **Unofficial project.** Teltonika Modbus Configurator is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments. It is aimed at larger installations where manually creating hundreds of Modbus requests, TCP Server mappings, and atvise Connect symbols becomes impractical.

## v0.5.0

v0.5 adds reusable register-table import profiles, XLS/XLSX/CSV support, atvise Connect Symbol import, verified HRD/DINT handling, and auto-hiding scrollbars throughout the large-project GUI.

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
- atvise Connect `.Symbol` export and import.
- Register-table import from `.xls`, `.xlsx`, and `.csv`.
- Built-in `Carel cDesign` and `Generic Modbus table` import profiles.
- Carel variable-name sanitizing and profile-specific `Index + 1` handling.
- Compact TCP Server allocation per Modbus address space after selective imports.
- Grouped/collapsible TCP Server Mappings view by source device.
- Double-click Edit, Ctrl/Shift multi-select Delete, and multi-select SCADA write-target creation.
- Auto-hiding vertical and horizontal scrollbars on large main tables and import previews.

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

## Register-table import profiles

Open:

```text
Import
├── Register table (XLS/XLSX/CSV)...
└── atvise Connect Symbol file...
```

The register-table importer first asks for a profile.

### Carel cDesign

The Carel profile recognizes columns such as:

```text
Types | Index | Size | Variable Name | DataType | Direction
```

Supported common Carel datatypes include `Bool`, `USInt`, `SInt`, `UInt`, `Int`, `UDInt`, `DInt` and `Real/FLOAT32`. Unsupported types are skipped rather than guessed.

The tested Carel project uses zero-based exported indexes, so the Carel profile defaults to:

```text
source Index + 1 -> RutOS request address
```

This is profile/device-specific and is not applied globally to every Modbus device.

### Generic Modbus table

The generic profile accepts common headers such as:

```text
Name / Point / Tag
Register / Address / Offset
Area / Memory / Register Type
Data Type / Encoding
Access / Rights
Count / Words
```

It keeps source addresses unchanged by default.

## atvise Connect Symbol import

A `.Symbol` file is treated strictly as node/register metadata. IP address, slave ID, serial settings, and other connection settings come from the existing RTU or TCP target device selected in the project.

Verified imported prefixes:

```text
IR   FC04 Input Register integer
IRR  FC04 Input Register FLOAT32
HR   FC03 Holding Register integer
HRR  FC03 Holding Register FLOAT32
DI   FC02 Discrete Input BOOL
DA   FC01 Coil BOOL
HRD  FC03 Holding Register signed INT32
```

`HRD` was verified against Carel scheduler DINT variables:

```text
byte order:      1234
request count:   2 registers
server width:    2 registers
```

A real 597-symbol atvise file was used during v0.5 acceptance testing; all entries became importable after HRD verification.

## Selective import and compact server blocks

Source registers may be sparse, but imported TCP Server mappings are compacted independently per Modbus address space. This avoids atvise Connect block reads across unmapped gaps.

For example:

```text
source Coil 110 -> TCP Coil 1025
source Coil 150 -> TCP Coil 1026
source Coil 151 -> TCP Coil 1027
source Coil 159 -> TCP Coil 1028
```

while the source requests still point to the correct physical registers.

## SCADA command / feedback workflow

RutOS derives TCP Server mapping permission from the source Modbus Client request. Read requests become Read-Only mappings and write requests become Write-Only mappings.

The project therefore uses separate feedback and command paths.

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

The write request is intentionally disabled. If enabled, RutOS can periodically transmit its configured placeholder value. With the request disabled, the write-only TCP Server mapping is still available for incoming SCADA writes.

New generated command mappings use a separate high address area (`20000+`) to stay away from normal read polling.

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

The project models mapping width separately from logical value count. For hardware-verified Carel/atvise HRD imports, the request uses two source registers for one signed 32-bit value.

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

Validated on a real RUT956 with Siemens RDF400MB over RS485, Carel controller over Modbus TCP, and atvise Connect as the upstream SCADA client, including separate read/write command paths.

### v0.5.0

Validated profile-driven Carel imports, real atvise Symbol import, Carel scheduler HRD/DINT values as signed INT32 `1234` with register count `2`, compact mapping allocation, and scrollbars across the main and import GUIs.

## Known limitations / next work

- No standalone Windows installer yet; installation uses Python/pip.
- 64-bit RutOS request datatype generation remains deferred until exact request tokens are verified.
- Import profiles only support semantics that have been defined explicitly; unknown vendor types are skipped rather than guessed.
- Live Modbus register testing is planned for v0.6.
- Carel `Direction` metadata is not treated as authorization to expose a SCADA write path; writable targets are selected deliberately.

See `CHANGELOG.md` for release history.
