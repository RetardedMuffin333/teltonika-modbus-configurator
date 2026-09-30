# Teltonika Modbus Configurator v0.8.0

v0.8.0 is the first colleague-ready internal release of the complete project workflow: create or import a project, batch and validate registers, test the proposed communication, deploy safely to RutOS, verify live values and writes, and export individual atvise symbols.

## Highlights

- First Project Wizard for RTU, TCP, and mixed projects.
- Carel cDesign and atvise `.Symbol` imports with preview, conflict handling, read-only/write-only choices, and register-by-register or batched modes.
- Safe automatic FC01/FC02/FC03/FC04 read batching that stops at source-address gaps.
- FC15/FC16 write batching with separate SCADA command mappings and preserved logical symbol names.
- Expandable physical batches showing every individual symbol, source register, datatype, and exported atvise address.
- Pre-import **Scan proposed batches** workflow for finding timeouts and `Illegal Data Address` responses before changing the project.
- Live Modbus Tester with Configured Read, Manual Read, Write Request, and Scan Device modes.
- Guarded live writes with complete command summaries and feedback/readback guidance.
- Read-only Gateway Preflight for RutOS model/firmware, Modbus configuration, services, runtime objects, listeners, and package information.
- Structured validation, generated-UCI preview, live diff, background deployment, local/remote backups, verification, and rollback.
- Bulk Device Generator that preserves physical batches and symbol-only aliases.
- Editable per-device atvise symbol groups, including separate `_w` write folders.
- Project Report and an expanded colleague-facing README/commissioning checklist.
- Persistent last-used gateway address without storing usernames or passwords.

## Hardware verification

The release workflow has been tested with:

- Teltonika RUT956 and earlier TRB145 testing;
- Siemens RDF400MB devices over Modbus RTU/RS485;
- a Carel controller over Modbus TCP;
- simultaneous RTU and TCP client operation;
- hundreds of Holding Registers plus Coil/Input data;
- BOOL, 16-bit, and FLOAT32 writes with readback;
- atvise Connect using individual exported symbols backed by physical RutOS batches;
- gateway/service restarts and continuous test-system operation.

For the tested large atvise project, Maximum read gap `0` and disabling the additional atvise Connect optimizer produced the most reliable update behavior.

## Upgrade

```powershell
git switch main
git pull
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tmc-gui.exe
```

Close the application before upgrading. Existing YAML projects remain the editable source of truth; run **Validate**, **Gateway preflight**, and **Preview live diff** before applying a configuration.

## Known limitations

- No standalone Windows installer yet; installation uses Python/pip.
- 64-bit RutOS request datatypes remain deferred until hardware verification.
- Unknown vendor datatypes are skipped instead of guessed.
- Carel direction metadata never creates write access without deliberate user selection.

## Safety

- Review the complete live diff before confirming apply.
- Never enable generated SCADA write requests for cyclic execution.
- Verify device, Unit ID, function, register, value, datatype, and byte order before every live write.
- Keep the final YAML project, Project Report, exported `.Symbol` file, and recovery snapshot name with the commissioning documentation.
