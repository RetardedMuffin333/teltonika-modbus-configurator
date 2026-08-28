from teltonika_modbus_configurator.models import Project, ServerMapping
from teltonika_modbus_configurator.register_allocator import next_free_register


def test_next_free_register_skips_second_word_of_float32():
    project = Project(mappings=[
        ServerMapping("Float", "Carel", "Temp", 1100, "holding_register", data_type="float32", count=1),
    ])
    assert next_free_register(project, register_type="holding_register", default=1025) == 1102
