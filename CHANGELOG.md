# Changelog

All notable changes to this project will be documented in this file.

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
- TCP mapping permissions: Read-Only (`r`), Write-Only (`w`) and Read-Write (`rw`).
- TCP mapping datatype/count metadata.
- Validation of function code against Modbus register area.
- Validation of read/write request direction against TCP mapping permissions.
- Bulk-generator support for write requests and writable mappings.
- Stable provenance/source IDs for imported connections, devices, requests and TCP mappings.
- Full add/edit/rename/delete support for imported live entities while retaining their RutOS UCI IDs.
- Editing of imported TCP Server settings.
- Preservation of unknown RutOS options in edited sections where possible.
- Deterministic ID allocation for newly added sections after the existing UCI range.
- Persistence of source IDs through YAML save/load.

### Changed

- Imported live projects are no longer restricted to append-only changes.
- Request and mapping GUI editors now expose write functions, write values and access permissions.
- Live-project generation rewrites only the intended existing UCI sections rather than reconstructing unrelated entities.
- Existing no-op import safety remains: import → no edits → byte-for-byte original UCI.

### Safety / compatibility

- Existing v0.1 read-only project behavior remains supported.
- Teltonika TCP Server mapping addresses remain limited to `1025..65536`.
- Unknown imported 32/64-bit request datatype tokens are retained losslessly instead of guessed or discarded.
- Modbus TCP Client source devices are still rejected on import when active because they are not yet modeled, preventing a lossy round trip.

### Release-candidate hardware validation

- Generated FC06 Write-Only command mapping structure was verified against the live TRB145 configuration model.
- Generated FC03 Read-Only feedback mapping to the same physical holding register was verified through the live diff path.
- Existing v0.1 hardware baseline remains a TRB145 running RutOS 7.24.2.

Final v0.2 hardware acceptance should be completed before the release branch is frozen.

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
