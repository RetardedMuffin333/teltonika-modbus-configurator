from teltonika_modbus_configurator.gui_usability import (
    selected_mapping_indices,
    selected_numeric_indices,
)


def test_selected_numeric_indices_are_unique_and_descending():
    assert selected_numeric_indices(("2", "5", "2", "bad", "1")) == [5, 2, 1]


def test_selected_mapping_indices_ignore_group_rows():
    selection = ("device::0", "mapping::4", "mapping::1", "mapping::4", "device::1")
    assert selected_mapping_indices(selection) == [4, 1]
