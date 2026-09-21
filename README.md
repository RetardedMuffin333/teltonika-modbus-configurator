# Teltonika Modbus Configurator

> **Unofficial project.** This is an independent open-source tool and is not affiliated with, endorsed by, or maintained by Teltonika Networks.

Teltonika Modbus Configurator is a desktop application for building, validating, testing, and deploying larger RutOS Modbus configurations. It is intended for installations where manually creating hundreds of Modbus requests, TCP Server mappings, and atvise Connect symbols would be slow and error-prone.

The application can combine Modbus RTU and Modbus TCP devices behind one Teltonika gateway and expose them through one Modbus TCP Server connection to atvise Connect or another SCADA system.

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

## What the configurator provides

- Modbus RTU and Modbus TCP Client devices in the same project.
- FC01, FC02, FC03, FC04, FC05, FC06, FC15, and FC16.
- Coil, Discrete Input, Holding Register, and Input Register server areas.
- 8/16-bit types and hardware-verified 32-bit INT, UINT, and FLOAT variants.
- Width-aware address allocation and collision detection.
- Automatic batching for large read lists.
- Separate feedback and SCADA command paths.
- Carel cDesign and generic XLS/XLSX/CSV register-table import.
- atvise Connect `.Symbol` import and export.
- Bulk generation of repeated RTU or TCP devices.
- YAML project save/load.
- Live RutOS configuration import over SSH.
- UCI preview, validation, live diff, guarded deployment, backups, and rollback.
- Read-only live diagnostics through the RutOS Web API.

## Installation

Python 3.11 or newer and Git are required.

On Windows PowerShell:

```powershell
git clone https://github.com/RetardedMuffin333/teltonika-modbus-configurator.git
cd teltonika-modbus-configurator
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

To update an existing installation:

```powershell
git switch main
git pull
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

Close the application before updating and start it again afterward.

## Recommended workflow

For a gateway that already contains a configuration:

1. Select **File → Import live TRB...** and enter the gateway SSH details.
2. Immediately select **File → Save As...** and save the imported project as YAML.
3. Make changes or import a register list.
4. Select **Validate** and resolve every error.
5. Select **Preview UCI** for a local preview.
6. Select **Deployment → Preview live diff...** and review the exact changes.
7. Select **Deployment → Apply to live TRB...** only when the diff is correct.
8. Re-import the live configuration or use the Live Modbus Tester to verify it.
9. Export the atvise `.Symbol` file and import it into atvise Connect.

For a new project, create the connections and devices manually or use an import/bulk workflow, then continue from validation. Passwords are requested when needed and are not stored in YAML.

## Main window

The tabs follow the data path through the gateway:

| Tab | Purpose |
| --- | --- |
| **Modbus Serial Clients** | RS485 interfaces: baud rate, parity, data bits, and stop bits. |
| **Devices & Requests** | Modbus RTU slave devices and their read/write requests. |
| **Modbus TCP Clients** | Ethernet Modbus endpoints, unit IDs, timing, and requests. |
| **TCP Server** | Upstream server port and Device ID used by SCADA. |
| **TCP Server Mappings** | Maps source requests into the four upstream address spaces. |

- **Save** stores the complete editable project as YAML.
- **Preview UCI** shows the RutOS configuration that would be generated.
- **Validate** checks references, functions, addresses, widths, collisions, and write requirements.

Use Ctrl/Shift for multi-selection and double-click a row to edit it.

## Core concepts

### Client request versus TCP Server mapping

A **client request** tells the Teltonika what to read from or write to on a field device. A **TCP Server mapping** exposes that value at an address read or written by SCADA. These addresses are independent:

```text
Carel holding register 241
        ↓ FC03 client request
Teltonika internal value
        ↓ TCP Server mapping
SCADA holding register 1025
```

Changing the server mapping address does not change the physical source register.

### Read and write paths

RutOS derives mapping access from the request function. Read requests create read-only mappings and write requests create write-only mappings. A writable SCADA value normally needs two paths.

| Value | Feedback request | Command request |
| --- | --- | --- |
| Coil / BOOL | FC01, enabled | FC05, disabled |
| 16-bit Holding Register | FC03, enabled | FC06, disabled |
| 32-bit INT/UINT/FLOAT | FC03, enabled | FC16, disabled |

Write requests must remain **disabled**. If an FC05/FC06/FC16 request is enabled, RutOS may periodically transmit its placeholder value without a SCADA command.

Select readable requests and use **Create write request(s)**. Generated command mappings use a separate range starting at `20000`, away from the normal read area starting at `1025`.

FC06 can write one 16-bit register only. The validator rejects FC06 with `int32`, `uint32`, or `float32`; those values require FC16 even though they represent one logical SCADA value.

## Read batching

### Why batching is recommended

One RutOS request and one deployed server mapping per symbol works for small projects but scales poorly. Large projects create excessive polling and slow atvise updates.

The recommended import mode groups compatible reads into bounded blocks:

- FC03/FC04: up to **100 registers** per request.
- FC01/FC02: up to **1000 bits** per request.
- A 32-bit value always remains entirely inside one block.
- Each function/address space is batched separately.

Source registers `225–242`, for example, become one request named `Batch_FC03_225_242`.

Only the physical batch request and block mapping are deployed to RutOS. Individual variable names, datatypes, and offsets remain as symbol aliases used for atvise export.

```text
One deployed batch mapping: Holding Registers 1025 ... 1042
        ├── AI_U9_Temperature .......... offset 0, FLOAT32
        ├── AI_U6_Temperature .......... offset 2, FLOAT32
        └── AI_U5_Outside_Temperature .. offset 16, FLOAT32
```

This is why the mapping view shows batches while the exported atvise file still contains individually named symbols.

### Batched versus register-by-register

Both register-table and Symbol imports offer:

- **Batched (recommended):** normal installations and large projects.
- **Register by register:** focused diagnostics, unusual devices, or very small lists.

Do not manually add individual mappings for symbols already represented by a batch. That duplicates the address path and removes the performance benefit.

## Carel cDesign import

Open **Import → Register table (XLS/XLSX/CSV)...** or the Carel-specific menu entry:

1. Select **Carel cDesign**.
2. Select the existing target Modbus TCP client.
3. Keep **Carel Index + 1 for RutOS request address** enabled for the tested Carel export.
4. Set the TCP Server mapping start; `1025` is the normal read default.
5. Select **Batched (recommended)**.
6. Build the import plan.
7. Review skipped/invalid rows, datatypes, directions, and addresses.
8. Select the required rows and import them.
9. Create write companions only for variables that genuinely need SCADA write access.
10. Validate the project.

Recognized columns include:

```text
Types | Index | Size | Variable Name | DataType | Direction
```

Common supported types include `Bool`, `USInt`, `SInt`, `UInt`, `Int`, `UDInt`, `DInt`, and `Real/FLOAT32`. Unknown types are skipped rather than guessed.

The `Index + 1` rule is a Carel profile default, not a global Modbus rule. Confirm it for other Carel exports or firmware.

## Generic register-table import

Select **Generic Modbus table** for non-Carel XLS/XLSX/CSV files. Common headers include:

```text
Name / Point / Tag
Register / Address / Offset
Area / Memory / Register Type
Data Type / Encoding
Access / Rights
Count / Words
```

The generic profile keeps addresses unchanged by default. Confirm whether the source document uses zero-based, one-based, or `4xxxx` notation.

## atvise Connect Symbol import

Open **Import → atvise Connect Symbol file...**.

A `.Symbol` file contains register metadata, not the device connection. First create/import the target RTU or TCP device with the correct IP, unit/slave ID, serial settings, timeout, and period.

1. Select the target device.
2. Set a source offset only when address bases differ.
3. Choose the server mapping start.
4. Select **Batched (recommended)**.
5. Build the plan and inspect conflicts/unrecognized lines.
6. Import the selected ready rows.
7. Validate and export a fresh `.Symbol` file from the finished project.

Verified prefixes:

| Prefix | Meaning |
| --- | --- |
| `IR` | FC04 Input Register integer |
| `IRR` | FC04 Input Register FLOAT32 |
| `HR` | FC03 Holding Register integer |
| `HRR` | FC03 Holding Register FLOAT32 |
| `HRD` | FC03 Holding Register signed INT32 |
| `DI` | FC02 Discrete Input BOOL |
| `DA` | FC01 Coil BOOL |

Hardware-verified Carel scheduler `HRD` values use signed INT32, byte order `1234`, and two registers per value.

## Exporting symbols to atvise

Use:

```text
Export
├── atvise Connect Symbol file (all mappings)...
└── atvise Connect Symbol file (enabled only)...
```

The export contains individual logical symbols, including aliases inside batches.

Recommended starting settings for the hardware-tested large batched project:

- Protocol: Modbus TCP.
- Slave address: Teltonika TCP Server Device ID, for example `101`.
- Start Address: match the exported-symbol addressing convention.
- Poll interval: start around `2000–5000 ms` and tune.
- Maximum read gap: `0` worked reliably.
- If a large configuration updates slowly or destabilizes the server, test **Disable optimizer completely**. With server-side batching enabled, the additional Connect optimizer was counterproductive on the tested RUT956.

Settings still depend on network latency, gateway model/firmware, and project size. Use the Live Modbus Tester to distinguish a gateway/request issue from Connect polling behavior.

## Bulk Device Generator

Open **Bulk → Bulk Device Generator...** when many devices share one structure, such as room thermostats with sequential slave IDs.

It can clone RTU/TCP templates, use sequential or explicit IDs, preserve relative offsets, allocate datatype-aware widths and separate read/write blocks, and detect collisions. Preview the batch and validate afterward.

## Live Modbus Tester

Open **Tools → Live Modbus Tester...**. It uses the gateway's RutOS Web API `test_request` path, so RTU tests still pass through the configured Teltonika RS485 interface.

| Mode | Use |
| --- | --- |
| **Existing Request** | Runs one configured request and shows timing, decoded value, and raw response. |
| **Ad-hoc Test** | Reuses a device as transport while allowing FC/register/count/datatype overrides. |
| **Device Scan** | Sequentially tests every enabled FC01–FC04 request; one failure does not stop the scan. |

The tester is read-only. Test writes through the normal SCADA write mapping and feedback readback.

## Validation

Run **Validate** before every deployment. Deployment is blocked while errors exist.

Checks include:

- existing connections, devices, requests, and mapping references;
- valid function/register combinations;
- values required by write requests;
- FC06 versus FC16 for 16-bit and 32-bit values;
- mapping permissions derived from request direction;
- datatype width and server-address collisions;
- generated mapping/alias dependencies.

Review warnings even when they do not block deployment.

## Deployment and rollback

### Preview UCI

Generates the local RutOS configuration without contacting a gateway.

### Preview live diff

**Deployment → Preview live diff...** reads the gateway over SSH and compares it with the project. Nothing is written.

### Apply

**Deployment → Apply to live TRB...** validates, reads the current configuration, shows the complete diff, requires typing `APPLY`, creates recovery data, writes the configuration, restarts the Modbus service, and verifies the result.

Network work runs in the background. Do not close the application or power off the gateway during apply/verification.

### Rollback

Use **Deployment → Rollback snapshot...** to restore a configurator snapshot. Confirm live communication afterward.

## Troubleshooting

### TCP Server is Up, but atvise shows Config err

- Confirm IP, port, slave address, and start-address convention.
- Confirm the symbol exists and its mapping is enabled.
- Allow Connect to rebuild its request cycle after a large change.
- Test the same request in **Live Modbus Tester → Existing Request**.
- If the tester is immediate but Connect is slow, investigate Connect polling/optimization.

### Values update only every 30–60 seconds

- Use batched import instead of individual deployed mappings.
- Keep Maximum read gap at `0` as the first baseline.
- Test **Disable optimizer completely** in Connect.
- Monitor one symbol temporarily; if it becomes fast, total cycle size causes the delay.
- Use Device Scan timings to estimate gateway response time.

### Device failure on only some symbols

- Check whether a request crosses an unsupported register.
- Verify source address, datatype width, byte order, and any `Index + 1`/offset.
- Confirm both registers of a 32-bit value are readable.
- Confirm the field device supports the selected function.

### Cannot delete a request

A request cannot be removed while mappings or symbol aliases reference it. Delete corresponding TCP Server mapping entries first. Generated aliases are cleaned with their mapping lifecycle; save/reopen and validate if a warning remains.

### Wrong FLOAT32 value

Use the byte/word order documented by the device. Supported verified permutations are `1234`, `2143`, `3412`, and `4321`.

## Addressing notes

- Documentation may call the same item offset `0`, register `1`, or `40001`. The configurator uses the numeric address required by RutOS.
- Read mappings normally start at `1025`; generated writes start at `20000`.
- The four server areas are separate and may use the same numeric address.
- Sparse source addresses may be exposed as compact server blocks without changing physical source addresses.
- A FLOAT32 is one logical value but occupies two 16-bit registers.

## Supported 32-bit RutOS tokens

```text
FLOAT32: 32bit_float1234, 32bit_float2143, 32bit_float3412, 32bit_float4321
INT32:   32bit_int1234,   32bit_int2143,   32bit_int3412,   32bit_int4321
UINT32:  32bit_uint1234,  32bit_uint2143,  32bit_uint3412,  32bit_uint4321
```

## CLI

The GUI is recommended for normal use. Command-line operations are also available:

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

## Tested deployment

The current workflow has been tested on a real RUT956 with:

- Siemens RDF400MB devices over RTU/RS485;
- a Carel controller over Modbus TCP;
- one upstream Modbus TCP connection to atvise Connect;
- hundreds of holding registers plus coils/inputs;
- batched reads;
- BOOL, 16-bit, and FLOAT32 writes with readback;
- gateway/service restarts and automatic reconnection;
- continuous operation of the test system.

Earlier versions were also tested on a TRB145 running RutOS 7.24.2.

## Safety

- Review the complete live diff before apply.
- Expose only write targets SCADA genuinely needs.
- Never enable generated write requests for cyclic execution.
- Keep a known-good YAML project and RutOS backup.
- Do not commit site UCI exports, backups, passwords, keys, or production project files.
- Test new datatype/function combinations on a test controller first.

## Known limitations

- No standalone Windows installer yet; installation uses Python/pip.
- 64-bit RutOS datatypes are deferred until exact tokens are verified.
- Unknown vendor datatypes are skipped rather than guessed.
- Live diagnostic writes are intentionally unavailable.
- Carel `Direction` metadata alone does not authorize a write path; select writable targets deliberately.

See `CHANGELOG.md` and the release notes for implementation history.
