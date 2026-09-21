from teltonika_modbus_configurator.mapping_lifecycle import (
    deployed_mappings_for_request,
    remove_server_mappings,
    remove_symbol_aliases_for_requests,
)
from teltonika_modbus_configurator.models import Project, ServerMapping


def _block_and_aliases() -> Project:
    return Project(mappings=[
        ServerMapping("Batch", "TP", "Batch", 1025, "holding_register", count=10, export_symbol=False),
        ServerMapping("Temperature", "TP", "Batch", 1025, "holding_register", deploy=False),
        ServerMapping("Setpoint", "TP", "Batch", 1033, "holding_register", deploy=False),
        ServerMapping("Other", "TP", "Other", 1100, "holding_register"),
    ])


def test_removing_batch_mapping_also_removes_its_symbol_aliases():
    project = _block_and_aliases()

    removed = remove_server_mappings(project, [0])

    assert removed == 3
    assert [mapping.name for mapping in project.mappings] == ["Other"]


def test_symbol_aliases_do_not_block_request_deletion():
    project = _block_and_aliases()
    remove_server_mappings(project, [0])
    project.mappings.extend([
        ServerMapping("LegacyAlias", "TP", "Batch", 1025, "holding_register", deploy=False),
    ])

    assert deployed_mappings_for_request(project, device_name="TP", request_name="Batch") == []
    assert remove_symbol_aliases_for_requests(project, device_name="TP", request_names={"Batch"}) == 1
    assert [mapping.name for mapping in project.mappings] == ["Other"]


def test_physical_mapping_still_blocks_request_deletion():
    project = _block_and_aliases()

    assert [mapping.name for mapping in deployed_mappings_for_request(
        project, device_name="TP", request_name="Batch"
    )] == ["Batch"]
