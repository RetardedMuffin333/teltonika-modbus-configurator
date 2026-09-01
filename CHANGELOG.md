# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0] - 2026-09-01

Sixth release baseline, focused on hardware-verified live Modbus diagnostics through the RutOS Web API.

### Added

- Live Modbus Tester under the existing `Tools` menu.
- One-shot live testing of existing project requests.
- RutOS Web API authentication with HTTP/HTTPS selection.
- Hardware-verified Modbus TCP live reads through RutOS.
- Hardware-verified Modbus RTU/RS485 live reads through RutOS.
- Response time, decoded value, raw response, and detailed RutOS validation errors.
- Ad-hoc read mode that reuses an existing configured RTU/TCP device as the transport template while overriding FC/register/count/datatype/byte order.
- Whole-device scan that sequentially tests every enabled FC01-FC04 request on the selected device.
- Scan result table with request, function, register, count, decoded value, response time, and status.
- Device scans continue after individual failures and can be stopped manually.

### Changed

- The v0.6 GUI entry point extends the existing Tools menu instead of creating a duplicate menu.
- RutOS bracketed scalar responses such as `[8.312500]` are normalized for display while raw JSON is preserved.
- RTU test requests inherit the actual project serial connection settings and send the RutOS device path (`/dev/rs485` or `/dev/rs232`).
- Live diagnostics remain deliberately read-only; FC05/FC06/FC15/FC16 diagnostic writes are deferred.

### Hardware verification

v0.6 acceptance testing used a real RUT956 with a Siemens RDF400MB thermostat over RS485/Modbus RTU and a Carel controller over Modbus TCP.

Verified end-to-end behavior includes:

- TCP FC01 Coil/BOOL reads;
- TCP FC03 Holding Register FLOAT32 reads;
- RTU FC04 reads through `/dev/rs485` using the configured serial settings;
- existing-request testing;
- ad-hoc reads on configured RTU and TCP devices;
- sequential whole-device scans across configured read requests.

## [0.5.0] - 2026-09-01

Fifth release baseline, focused on reusable import profiles, broader register-table formats, atvise Connect Symbol import, and large-project GUI polish.

### Added

- Register-table import from `.xls`, `.xlsx`, and `.csv` through one normalized parsing pipeline.
- Reusable `ImportProfile` abstraction for vendor-specific column aliases, name normalization, and address-offset defaults.
- Built-in `Carel cDesign` profile with hardware-tested `Index + 1` default.
- Built-in `Generic Modbus table` profile for common `Name/Register/Area/Data Type/Access/Count` style exports with no automatic address offset.
- atvise Connect `.Symbol` import targeting an existing RTU or TCP client in the project.
- Symbol import support for `IR`, `IRR`, `HR`, `HRR`, `DI`, `DA`, and hardware-verified `HRD`.
- Hardware-verified `HRD` interpretation as FC03 Holding Register, signed 32-bit integer, byte order `1234`, request register count `2`.
- Compact, datatype-aware TCP Server allocation for imported Symbol rows, including two-register widths for 32-bit values.
- Auto-hiding vertical and horizontal scrollbars for all large main GUI tables.
- Auto-hiding scrollbars in Symbol import and Register Table import previews.

### Changed

- Import workflows are grouped under a single `Import` menu.
- Carel import is no longer tied to a single legacy XLS parser; the same profile works across XLS, XLSX and CSV.
- Register-table profile selection is explicit before opening the source file.
- Symbol import treats the Symbol file strictly as register/node metadata; connection settings continue to come from the selected existing project device.
- Large main tables preserve the v0.4 usability features while adding scrollbars only when content exceeds the visible area.

### Verified behavior

v0.5 acceptance testing used real project data and a working Teltonika/Carel setup.

Verified end-to-end behavior includes:

- Carel cDesign register-table import through the profile-driven importer.
- atvise Connect Symbol parsing of a real 597-symbol file with zero unrecognized register lines.
- `HRD` scheduler variables such as Carel `DINT` values imported as 32-bit signed Holding Register requests using byte order `1234` and register count `2`.
- All 597 entries in the tested Symbol file becoming importable after HRD verification.
- Compact server-side repacking remaining compatible with atvise Connect block reads.
- Main application, Symbol preview, and Register Table preview scrollbars tested interactively.

### Deferred to v0.6+

- Live Modbus register tester from the desktop GUI.
- Direct one-shot reads from existing project requests.
- Manual diagnostic writes from the tester.
- Standalone Windows installer.
- 64-bit RutOS request datatype generation until exact request tokens are verified.

## [0.4.0] - 2026-09-01

Fourth release baseline, focused on Carel cDesign import, large-project usability, and hardware-verified SCADA write workflows for coils, 16-bit holding registers, and FLOAT32 values.

### Added

- Native Carel cDesign legacy `.xls` import using `xlrd`.
- Detection of cDesign documentation columns such as `Types`, `Index`, `Size`, `Variable Name`, `DataType`, and `Direction`.
- Carel variable-name sanitizing: `.` becomes `_`; square brackets are removed (`Msk[1]` -> `Msk1`).
- Explicit Carel `Index + 1` option for tested zero-based Carel addressing.
- Carel datatype conversion for common `Bool`, `USInt`, `SInt`, `UInt`, `Int`, `UDInt`, `DInt`, and `Real/FLOAT32` values.
- Selective/filterable Carel import rather than mandatory whole-table import.
- Repacking of selected Carel mappings into compact TCP Server blocks per Modbus address space.
- Grouped/collapsible TCP Server Mappings UI by source device.
- Expand-all / collapse-all controls for mapping groups.
- Double-click Edit for RTU requests, TCP requests, and TCP Server mappings.
- Ctrl/Shift multi-select Delete for requests and mappings.
- Multi-select SCADA write-target creation.
- SCADA write companion support for FC01 -> disabled FC05 coils.
- SCADA write companion support for FC03 -> disabled FC06 8/16-bit holding-register values.
- SCADA write companion support for FC03 -> disabled FC16 32-bit/FLOAT32 holding-register values.
- Separate high write-only mapping area (`20000+`) for newly generated command targets so large read blocks do not collide with write-only mappings.

### Changed

- Carel `Direction=ReadWrite` is treated as metadata, not as automatic authorization to expose a SCADA command path.
- Recommended Carel workflow is read import first, followed by explicit selection of actual commands/setpoints for write-target generation.
- TCP Server Mappings view now scales cleanly to projects with 100+ mappings.
- Selected sparse Carel rows are compacted again at import time so omitted rows do not leave server-side gaps.
- Existing v0.3 read/write layouts remain compatible.

### Hardware verification

v0.4 acceptance testing used a real RUT956 with:

- Siemens RDF400MB thermostat over RS485/Modbus RTU;
- Carel controller over Modbus TCP;
- both sources aggregated through one RutOS Modbus TCP Server;
- atvise Connect as the upstream SCADA client.

Verified end-to-end behavior includes:

- Carel cDesign `.xls` -> importer -> RutOS TCP-client requests -> TCP Server mappings -> atvise Connect.
- Carel BOOL/Coil reads through FC01.
- Carel 16-bit Holding Register reads through FC03.
- Carel FLOAT32 Holding Register reads through FC03.
- SCADA Coil writes through a disabled FC05 request with FC01 feedback.
- SCADA 16-bit Holding Register writes through a disabled FC06 request with FC03 feedback.
- SCADA FLOAT32 Holding Register writes through a disabled FC16 request with FC03 feedback.
- Compact Coil mappings fixed atvise `Sensor failure` caused by block reads across unmapped gaps.
- Carel source addressing on the tested project required `Index + 1` in RutOS.
- Grouped mapping UI, double-click edit, multi-select delete, and multi-select write-target creation were tested in the working project.

### Deferred to v0.5+

- Standalone Windows installer.
- Broader Carel XLSX/CSV import support.
- 64-bit request datatype generation until exact RutOS request tokens are verified.
- Additional importer profiles for other controller/vendor exports.

## [0.3.0] - 2026-08-31

Third release baseline, focused on mixed RTU/TCP aggregation, verified 32-bit datatypes, improved bulk generation, and a hardware-verified SCADA write path.

### Added

- Modbus TCP Client devices alongside RTU devices in the same project and RutOS gateway.
- Fresh RutOS UCI generation and live import/edit support for TCP client devices.
- Verified 32-bit request datatype tokens for FLOAT32, INT32 and UINT32 using byte orders `1234`, `2143`, `3412`, `4321`.
- Datatype-aware TCP mapping widths so 32-bit values reserve two 16-bit Modbus addresses.
- atvise Connect symbol export for verified `DI`, `DA`, `IRR`, `HRR` and `HRD` forms in addition to integer `IR`/`HR`.
- Workflow-oriented GUI tab order: Serial Clients -> Devices & Requests -> TCP Clients -> TCP Server -> TCP Server Mappings.
- SCADA menu action to create a write companion from an FC03 feedback request.
- Hardware-verified FC03 feedback + disabled FC06 command pattern.
- Dedicated write-only TCP Server mapping allocation starting at HR1200 by default.
- SCADA-aware Bulk Generator allocation that keeps read and write-only holding-register blocks separate.

### Changed

- Bulk Generator now supports both RTU and TCP-client templates.
- Bulk transport controls are context-sensitive for serial vs TCP devices.
- Template mapping allocation uses first-fit contiguous free ranges, allowing intentional gaps to be reused instead of always appending after the highest existing register.
- Template-relative mapping offsets are preserved independently per Modbus address space.
- Width-aware first-fit allocation prevents FLOAT32/INT32/UINT32 collisions.
- The main GUI entry point now includes the SCADA helper workflow.

### Hardware verification

The v0.3 acceptance work used a mixed RutOS setup with Siemens RDF400MB over RS485 and a Carel controller over Modbus TCP, both exposed through one RutOS Modbus TCP Server to atvise Connect.

Verified behavior included RTU thermostat reads, Carel FLOAT32 reads, atvise writes through disabled FC06 requests, FC03 feedback, and bulk-generated command/feedback pairs across multiple thermostat devices.

## [0.2.0] - 2026-08-20

Second release baseline, focused on write support and safe editing of imported live configurations.

### Added

- FC05, FC06, FC15 and FC16 write support.
- Separate write value semantics.
- Automatic mapping access derived from request direction.
- Stable source IDs for imported connections/devices/requests/mappings.
- Editing, renaming and deleting imported entities while retaining UCI identities.
- All four TCP Server Modbus areas.

### Changed

- Imported live projects are no longer restricted to append-only changes.
- Request editors expose write functions and values.
- Mapping access follows RutOS behavior and is not manually editable.

## [0.1.0] - 2026-08-18

First proven end-to-end release baseline.

### Added

- Device-agnostic serial Modbus RTU project model.
- FC01-FC04 read requests.
- RutOS Modbus TCP Server mappings.
- Tkinter GUI.
- YAML save/load.
- Live RutOS import over SSH.
- Bulk Device Generator.
- UCI preview, live diff, guarded Apply, backups and rollback.
- atvise Connect `.Symbol` export for verified Input Register and Holding Register mappings.

### Verified on hardware

Validated on a real TRB145 running RutOS 7.24.2 with a generated 23-device RTU project.
