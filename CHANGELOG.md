# Changelog

All notable changes to this project will be documented in this file.

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
