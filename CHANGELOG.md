# Changelog

All notable changes to this project will be documented in this file.

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
- Importing a live project and making no changes now produces an exact zero diff.
- Existing imported section IDs, ordering and `tag_id` relationships are no longer regenerated unnecessarily.
- v0.1.0 imported-project deployment is intentionally append-only to prevent accidental reconstruction of existing live entities.
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

### Deferred to later versions

- Modbus TCP Client devices.
- Mixed RTU + TCP-client aggregation in one project.
- Full editing/replacement of existing imported entities.
- Additional unverified RutOS options.
- Verified atvise Coil / Discrete Input symbol syntax.
- Installer/packaging beyond editable Python installation.
- Reusable template libraries/catalogs.
