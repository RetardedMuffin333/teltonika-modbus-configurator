# Teltonika Modbus Configurator v0.7.0

v0.7 turns the configurator into a scalable workflow for large Carel/atvise projects. The release combines hardware-tested read batching, reliable SCADA write paths, responsive live deployment, consistent import/export behavior, and a shareable Project Report.

## Highlights

### Scalable batched reads

Carel register-table and atvise `.Symbol` imports can now create bounded physical blocks:

- FC03/FC04: up to 100 registers per request;
- FC01/FC02: up to 1000 bits per request;
- 32-bit values are never split across batch boundaries.

RutOS receives one physical request/mapping per batch. Individual variable names, offsets, and semantic datatypes remain available as aliases for atvise symbol export. Users can still choose **Register by register** for small or diagnostic configurations.

### Verified SCADA writes

The release supports separate command and feedback paths:

- FC05 for BOOL/Coil commands;
- FC06 for 8/16-bit Holding Register commands;
- FC16 for INT32, UINT32, and FLOAT32 commands.

Generated write requests remain disabled so RutOS only executes them when triggered through the write-only TCP Server mapping. Validation now rejects unsafe FC06 use with multi-register datatypes.

### Responsive live deployment

Preview, apply, and rollback network operations run outside the Tk main thread. The application remains responsive and reports deployment stages while it connects, reads, writes, restarts the Modbus service, and verifies the final live configuration.

### Project Report

**Tools → Project Report...** produces a read-only summary containing:

- RTU/TCP device and request counts;
- physical batches and logical symbols;
- estimated requests avoided by batching;
- enabled functions and occupied server blocks;
- workload per source device;
- validation results;
- warnings for cyclically enabled write requests.

Reports can be saved as TXT or copied to the clipboard for commissioning documentation and support.

### Colleague-facing documentation

README now provides a complete operating guide for installation, live import, project editing, Carel and Symbol imports, batching, write creation, atvise Connect setup, testing, validation, deployment, rollback, and troubleshooting.

## Hardware acceptance

Acceptance testing was performed on a continuously running RUT956 test setup with Siemens RDF400MB devices over RS485, a Carel controller over Modbus TCP, and atvise Connect as the upstream client.

Verified behavior includes:

- hundreds of Holding Registers plus Coil/Input data;
- stable batched read operation;
- individual atvise symbol access through batch aliases;
- BOOL, 16-bit, and FLOAT32 writes with feedback readback;
- restart and reconnection behavior;
- continuous operation of the test system.

For the tested large project, atvise Connect performed best with Maximum read gap `0` and **Disable optimizer completely** enabled because batching is already handled by the Teltonika configuration.

## Verification

- 188 automated tests pass.
- Python modules compile successfully.
- Documentation and generated changes pass `git diff --check`.

## Deferred

- First Project Wizard is planned for v0.8.
- The Windows installer remains planned after the guided workflow is complete.
- 64-bit RutOS datatype generation remains deferred until exact tokens are verified on hardware.
