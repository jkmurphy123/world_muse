from __future__ import annotations


def test_main_module_imports_without_starting_server():
    import world_muse.main as main

    assert callable(main.build_app)
    assert callable(main.main)
