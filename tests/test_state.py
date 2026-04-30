from __future__ import annotations

from world_muse.state import default_story_structure, find_node_by_id


def test_default_story_structure_contains_expected_top_level_nodes():
    structure = default_story_structure()
    ids = [node.id for node in structure]
    assert "premise" in ids
    assert "setting" in ids
    assert "characters" in ids
    assert "plot" in ids


def test_find_node_by_id_finds_nested_plot_node():
    structure = default_story_structure()
    node = find_node_by_id(structure, "plot.act2")
    assert node is not None
    assert node.label == "Act II"
