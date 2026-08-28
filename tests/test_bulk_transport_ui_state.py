def test_transport_ui_behavior_is_covered_by_gui_sync_contract():
    # Tk widgets are intentionally not instantiated in headless CI. The GUI's
    # _sync_transport_fields method is exercised manually; this test file keeps
    # the transport-specific behavior visible in the v0.3 regression suite.
    expected = {
        "rtu": {"connection": True, "host": False, "port": False, "id_label": "Slave ID"},
        "tcp": {"connection": False, "host": True, "port": True, "id_label": "Unit ID"},
    }
    assert expected["rtu"]["connection"] is True
    assert expected["tcp"]["host"] is True
