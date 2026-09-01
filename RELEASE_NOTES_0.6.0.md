# Teltonika Modbus Configurator v0.6.0

v0.6 adds hardware-verified live Modbus diagnostics to the desktop GUI using the RutOS Web API.

## Added

- Live Modbus Tester under the existing `Tools` menu.
- One-shot testing of existing project requests.
- Hardware-verified Modbus TCP live reads through RutOS.
- Hardware-verified Modbus RTU/RS485 live reads through RutOS.
- RutOS Web API login with HTTP/HTTPS selection.
- Human-readable RutOS validation errors for failed test requests.
- Response-time, decoded-value, and raw-response display.
- Ad-hoc read testing that reuses an existing configured device as the transport template while allowing FC/register/count/datatype/byte-order overrides.
- Whole-device scan that sequentially tests all enabled FC01-FC04 requests on a selected device.
- Device-scan result table with request name, function, register, count, decoded value, response time, and status.
- Device scans continue after individual request failures and include a stop control.

## Hardware verification

Acceptance testing was performed on a real RUT956 with:

- Siemens RDF400MB over RS485/Modbus RTU;
- Carel controller over Modbus TCP;
- live reads executed from the desktop configurator through the RutOS `test_request` API.

Verified behavior includes:

- TCP FC01 Coil/BOOL reads;
- TCP FC03 Holding Register FLOAT32 reads;
- RTU FC04 reads through `/dev/rs485` using the actual project serial settings;
- normalized RutOS responses such as `[8.312500]` -> `8.312500`;
- ad-hoc reads on configured RTU/TCP devices;
- sequential whole-device scans across configured read requests.

## Safety scope

v0.6 live diagnostics are intentionally read-only. FC05, FC06, FC15, and FC16 diagnostic writes are not exposed by the tester. Normal SCADA command/write workflows remain unchanged.

## Known limitations

- No standalone Windows installer yet; installation remains Python/pip based.
- 64-bit RutOS request datatype generation remains deferred until exact request tokens are verified.
- Live diagnostic writes are intentionally deferred to a future version if they prove useful for commissioning.
