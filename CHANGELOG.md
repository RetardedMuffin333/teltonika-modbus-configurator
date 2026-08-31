# Changelog

All notable changes to this project will be documented in this file.

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

Verified behavior included:

- RTU thermostat values read correctly through the aggregated TCP Server.
- Carel FLOAT32 data read correctly through the RutOS Modbus TCP Client path.
- Device-specific Carel zero-based register numbering was handled by using the required address offset in the project rather than globally in the application.
- atvise Connect successfully wrote to a RutOS Write-Only holding register backed by a disabled FC06 request.
- The same physical thermostat register was polled through an enabled FC03 request and returned the written value as feedback.
- Keeping Read-Only HR mappings around `HR1031+` and Write-Only mappings around `HR1200+` prevented atvise Connect block-read failures caused by including a Write-Only address in an FC03 read block.
- Bulk-generated thermostat clones retained the paired read/write architecture and were tested successfully on hardware.

### Deferred to v0.4+

- Carel cDesign register-table import for large projects.
- 64-bit request datatype generation until exact RutOS request tokens are verified.
- Additional SCADA write companion patterns beyond the hardware-verified single-register FC03 + FC06 case.
- Standalone Windows installer.

## [0.2.0] - 2026-08-20

Second release baseline, focused on write support and safe editing of imported live configurations.

### Added

- Modbus write function support:
  - FC05 Set single coil
  - FC06 Set single holding register
  - FC15 Set multiple coils
  - FC16 Set multiple holding registers
- Separate write `value/values` semantics instead of treating the field as a read count.
- Request datatype generation for 8-bit INT/UINT, 16-bit INT/UINT with high/low-byte-first ordering, Bool, ASCII, Hex and PDU where supported.
- Lossless preservation of imported RutOS request datatype tokens that are not yet decoded by the configurator.
- All four TCP Server Modbus areas: Coil, Discrete Input, Holding Register and Input Register.
- Automatic TCP mapping access derived from the source request: FC01–FC04 → Read-Only (`r`), FC05/06/15/16 → Write-Only (`w`).
- TCP mapping datatype/count metadata.
- Validation of function code against Modbus register area.
- Validation of automatically derived mapping access against request direction.
- Bulk-generator support for write requests and writable mappings.
- Stable provenance/source IDs for imported connections, devices, requests and TCP mappings.
- Full add/edit/rename/delete support for imported live entities while retaining their RutOS UCI IDs.
- Editing of imported TCP Server settings.
- Preservation of unknown RutOS options in edited sections where possible.
- Deterministic ID allocation for newly added sections after the existing UCI range.
- Persistence of source IDs through YAML save/load.

### Changed

- Imported live projects are no longer restricted to append-only changes.
- Request editors expose write functions and write values.
- Mapping access is displayed but no longer editable, matching RutOS WebUI behavior.
- Live-project generation rewrites only the intended existing UCI sections rather than reconstructing unrelated entities.
- Existing no-op import safety remains: import → no edits → byte-for-byte original UCI.

### Safety / compatibility

- Existing v0.1 read-only project behavior remains supported.
- Teltonika TCP Server mapping addresses remain limited to `1025..65536`.
- Unknown imported 32/64-bit request datatype tokens are retained losslessly instead of guessed or discarded.
- Modbus TCP Client source devices are still rejected on import when active because they are not yet modeled, preventing a lossy round trip.
- Existing mapping source IDs are retained when mappings are edited through the GUI.

### Hardware baseline

- The proven deployment baseline remains a real TRB145 running RutOS 7.24.2.
- v0.2 generated read/write UCI structures and live diffs were checked against the live RutOS configuration model.

### Deferred

- Modbus TCP Client devices and mixed RTU + TCP-client aggregation.
- Fresh generation of every 32/64-bit request byte-order variant until exact RutOS UCI tokens are verified.
- Verified atvise Coil/Discrete Input/float/double symbol forms (`DI`, `DA`, `IRR`, `HRR`, `HRD`, etc.).
- Standalone Windows installer.
- Reusable template catalogs and richer bulk-edit operations.

## [0.1.0] - 2026-08-18

First proven end-to-end release baseline.

### Added

- Device-agnostic project model for serial Modbus RTU deployments.
- FC01, FC02, FC03 and FC04 read requests.
- RutOS Modbus TCP Server mappings with generated `tag_id` relationships.
- Tkinter desktop GUI for Windows/Linux Python environments.
- YAML project save/load.
- Live RutOS import over SSH.
- Import from exported `modbus_client` and `modbus_server` UCI packages.
- Bulk Device Generator using an existing device as a template.
- Sequential and explicit/non-sequential Slave ID support.
- Automatic next-free TCP register allocation.
- Collision validation for names, Slave IDs and TCP mappings.
- Teltonika TCP register range validation (`1025..65536`).
- Generated UCI preview.
- Live unified diff preview before deployment.
- Guarded live Apply with explicit confirmation.
- Local and remote deployment backups.
- Remote rollback snapshot support.
- atvise Connect `.Symbol` export for verified Input Register (`IR`) and Holding Register (`HR`) mappings.
- Separate symbol export modes for all mappings and enabled-only mappings.

### Safety fixes

- Imported live configurations preserve their original UCI provenance.
- Importing a live project and making no changes produces an exact zero diff.
- Existing imported section IDs, ordering and `tag_id` relationships are not regenerated unnecessarily.
- v0.1.0 imported-project deployment is intentionally append-only.
- New imported-project entities are allocated above the existing UCI ID range.

### Verified on hardware

The release was tested on a real Teltonika TRB145 running RutOS 7.24.2.

The final acceptance test used a fresh generated project containing 23 Modbus RTU devices with three requests per device and the corresponding Modbus TCP Server mappings. The configuration was deployed from the configurator, accepted by RutOS, appeared correctly in the WebUI and worked live.

The tested request pattern included:

```text
Temperature  FC04 / 515
Setpoint     FC04 / 554
On/Off       FC03 / 262
```

The tested mapping pattern used separate Input Register and Holding Register blocks beginning at Teltonika TCP addresses 1025, 1050 and 1080.
