# Carel cDesign register import (v0.4 development)

The first v0.4 milestone is intentionally non-destructive: inspect a native
Carel cDesign Excel 97-2003 (`.xls`) Modbus export and preview the table the
configurator detects before generating any RutOS requests.

## Preview workflow

1. Export the Modbus documentation/register list from Carel cDesign as `.xls`.
2. Run the v0.4 development GUI.
3. Open `Carel -> Carel cDesign XLS preview...`.
4. Select the exported workbook.
5. Verify the detected sheet, header row, variable name, register, datatype and
   access columns.

The importer uses `xlrd` for the legacy binary XLS format. The parser scans the
first rows of each worksheet for likely name/register/type/access headers and
chooses the sheet with the most candidate register rows.

No project configuration is changed by the preview action.

## Next milestone

After the real cDesign export structure is verified, the preview rows will be
converted into Modbus TCP Client requests and compact RutOS TCP Server mappings.
Carel's device-specific address offset (for example a documented register 240
being requested as 241 in RutOS on the tested controller) will be an explicit
import option rather than a global address rule.
