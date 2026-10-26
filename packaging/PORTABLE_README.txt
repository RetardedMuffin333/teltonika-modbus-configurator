Teltonika Modbus Configurator - Windows x64 portable

QUICK START
1. Extract the ENTIRE ZIP to a writable local folder.
2. Open the extracted TeltonikaModbusConfigurator folder.
3. Double-click TeltonikaModbusConfigurator.exe.
Keep _internal next to the EXE. Do not launch from inside the ZIP or copy only the EXE.
No Python, Git, installer, or administrator rights are required.

WORKFLOW
Open/create a YAML project -> gateway preflight -> prepare/import requests
-> scan proposed read batches -> validate -> review live diff -> apply
-> verify live reads/writes -> export atvise Symbol file.
See README.md for the full operating guide. examples/basic.yaml is an
illustrative disabled-device project; adapt it to your own hardware.

SETTINGS AND PROJECTS
This is a no-install package. Preferences and logs still use your Windows profile:
%LOCALAPPDATA%\Teltonika Modbus Configurator\preferences.json
%LOCALAPPDATA%\Teltonika Modbus Configurator\logs\application.log
The application remembers the gateway address, not passwords.
Save YAML projects in your own project folder, outside the application folder.

UPGRADE
Close the app, extract the new ZIP to a new folder, and open your saved YAML.
Your profile preferences remain available. Keep the previous package for rollback.

SUPPORT
If the app fails, send the version from VERSION.txt and the relevant log excerpt.
Review logs before sharing: errors may contain site paths or device information.
This internal build is not code-signed; Windows may identify an unknown publisher.
Follow your company's software approval policy if execution is blocked.

WINDOWS CHECK BEFORE FIELD USE
Open/save YAML; import Excel and Symbol; export Symbol; gateway preflight;
live read/write with readback; deploy and verify on a TEST gateway.
