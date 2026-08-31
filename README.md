# Teltonika Modbus Configurator

> **Unofficial project.** Teltonika Modbus Configurator is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

A device-agnostic configuration tool for Teltonika RutOS Modbus deployments. It is aimed at larger installations where manually creating hundreds of Modbus requests, TCP Server mappings, and atvise Connect symbols becomes impractical.

## v0.3.0

v0.3 adds mixed Modbus RTU + Modbus TCP Client aggregation, verified 32-bit request datatypes, improved bulk allocation, workflow-oriented GUI tabs, richer atvise symbol export, and the hardware-verified SCADA command/feedback workflow.

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
- Separate read-count and write-value semantics.
- Request datatypes including 8/16-bit integers and verified 32-bit INT/UINT/FLOAT byte orders.
- Verified RutOS FLOAT32 byte-order tokens: `1234`, `2143`, `3412`, `4321`.
- All four Modbus TCP Server areas: Coil, Discrete Input, Holding Register and Input Register.
- Mapping access derived automatically from source request direction: reads -> `r`, writes -> `w`.
- Width-aware mapping collision detection and allocation for 32-bit values.
- Live RutOS import over SSH with source-UCI provenance retained.
- Exact no-op round trip for imported configurations.
- Editing, adding and deleting imported RTU/TCP devices, requests and mappings while retaining stable UCI identities.
- YAML save/load.
- Exact UCI preview and live diff.
- Guarded SSH deployment with local/remote backups and rollback snapshots.
- Bulk Device Generator for both RTU and TCP clients.
- Template cloning with first-fit gap reuse instead of always appending after the highest register.
- Separate compact allocation of read and SCADA write-only blocks.
- atvise Connect `.Symbol` export for verified `IR`, `HR`, `DI`, `DA`, `IRR`, `HRR` and `HRD` forms where supported.
- Dedicated SCADA helper for generating paired FC03 feedback + disabled FC06 write targets.
- Windows/Tkinter desktop GUI with workflow-oriented tabs.

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

The main tabs follow the actual data path:

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
create requests
        ↓
create TCP Server mappings
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

v0.3 can aggregate serial and Ethernet Modbus devices behind one RutOS Modbus TCP Server connection.

A hardware-tested example is:

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

This allows SCADA to use a single Teltonika Modbus TCP connection while the gateway polls both RTU and TCP source devices.

## SCADA command / feedback workflow

RutOS derives a TCP Server mapping's permission from the source Modbus Client request. A source FC03 becomes Read-Only and a source FC06 becomes Write-Only.

For a SCADA-controlled command, v0.3 uses separate read and write paths to the same physical register:

```text
READ / feedback
physical device HR101
       ↓ FC03, enabled
RutOS TCP HR1031, Read-Only
       ↓
atvise CMD_Oper_Mode

WRITE / command
atvise CMD_Oper_Mode_w
       ↓ write TCP HR1200
RutOS TCP HR1200, Write-Only
       ↓ FC06, disabled
physical device HR101
```

The FC06 request is intentionally **disabled**. If enabled, RutOS would periodically transmit the configured placeholder value. With it disabled, the write-only TCP Server mapping is still available for incoming SCADA writes, and the incoming value becomes the runtime FC06 command.

### Create a write target

Select an existing FC03 feedback request and use:

```text
SCADA
└── Create write target from selected RTU request
```

or the corresponding TCP-client action.

For example, an existing:

```text
CMD_Oper_Mode
FC03
physical register 101
enabled
TCP mapping HR1031
```

produces:

```text
CMD_Oper_Mode_w
FC06
physical register 101
disabled
TCP mapping HR1200
Access = Write-Only
```

Write mappings start at `HR1200` by default so they remain separated from normal read blocks.

### Why the separate HR1200+ block matters

During hardware testing, placing a Write-Only mapping immediately after Read-Only holding registers caused atvise Connect to combine them into one FC03 block read. Because the write-only address cannot be read, the complete block returned `Sensor failure`.

Keeping the blocks separate avoids that failure:

```text
READ feedback
HR1031..HR1033

WRITE commands
HR1200..HR1202
```

The write-only symbol itself may show a read-side `Sensor failure` in a client that insists on polling it; that does not prevent writing to it. Read feedback should be taken from the corresponding FC03 mapping.

## Bulk Generator

The Bulk Generator can clone RTU or TCP-client templates, including requests and TCP Server mappings.

It supports:

- sequential or explicit Slave/Unit IDs;
- RTU and TCP transports;
- datatype/byte-order aware mappings;
- first-fit free-range allocation;
- 32-bit mapping width accounting;
- preservation of template-relative offsets;
- separate address spaces for IR/HR/DI/Coil;
- separate compact read and SCADA write-only holding-register blocks.

Example hardware-tested template layout:

```text
                 READ feedback       WRITE commands
RDF_Test         HR1031-HR1033        HR1200-HR1202
RDF_Test_02      HR1034-HR1036        HR1203-HR1205
RDF_Test_03      HR1037-HR1039        HR1206-HR1208
```

A later mapping such as a Carel FLOAT32 value at `HR1100-HR1101` does not force new thermostat mappings above it if a sufficiently large free gap exists below it.

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

A single FLOAT32 value uses RutOS request `reg_count=1`, while its TCP Server mapping occupies two 16-bit Modbus register addresses for allocation/collision purposes.

Device register numbering remains device-specific. For example, a Carel register documented with zero-based numbering may need `documented address + 1` in RutOS. The configurator does not apply such offsets globally.

## atvise Connect symbol export

The exporter uses the configured TCP Server mappings, avoiding a second manual register list.

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

Existing RutOS configurations can be imported over SSH. Imported projects retain the original `modbus_client` and `modbus_server` packages plus stable source IDs. With no edits, generation returns the original UCI byte-for-byte.

Recommended live workflow:

```text
Import live RutOS
      ↓
Save YAML
      ↓
Validate
      ↓
Edit / bulk generate
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

Added write-request generation, automatic mapping access and stable editing of imported live UCI while retaining the v0.1 deployment baseline.

### v0.3.0

v0.3 was tested with a mixed RTU + Modbus TCP configuration on RutOS hardware, including:

- Siemens RDF400MB over RS485/Modbus RTU;
- Carel controller over Modbus TCP;
- both sources aggregated through one RutOS Modbus TCP Server;
- FLOAT32 Carel values through the TCP client path;
- atvise Connect reading the aggregated server;
- SCADA writes through a disabled FC06 request and Write-Only TCP mapping;
- FC03 feedback confirming the written thermostat value;
- Bulk Generator cloning the same paired command/feedback architecture across multiple thermostat devices.

The key write-path behavior was verified end-to-end on hardware, not only from generated UCI.

## Known limitations / next work

- No standalone Windows installer yet; installation uses Python/pip.
- 64-bit request datatype generation is still deferred until exact RutOS request tokens are verified.
- Some atvise symbol datatype forms remain intentionally rejected rather than guessed.
- SCADA helper currently focuses on the hardware-verified single-register FC03 + FC06 workflow.
- Carel register-table import is planned for v0.4 so large cDesign exports can generate requests and TCP Server mappings without manual entry.

See `CHANGELOG.md` for release history.
