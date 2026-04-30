from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StoryNode:
    id: str
    label: str
    summary: str = ""
    details: dict[str, str] = field(default_factory=dict)
    children: list["StoryNode"] = field(default_factory=list)


def default_story_structure() -> list[StoryNode]:
    return [
        StoryNode("premise", "Premise", "Core concept and narrative promise."),
        StoryNode("setting", "Setting", "World rules, tone, geography, and cultural context."),
        StoryNode("characters", "Characters", "Primary cast and motivations."),
        StoryNode(
            "plot",
            "Plot",
            "High-level progression and major turning points.",
            children=[
                StoryNode("plot.act1", "Act I", "Setup and inciting incident."),
                StoryNode("plot.act2", "Act II", "Escalation and midpoint reversal."),
                StoryNode("plot.act3", "Act III", "Climax and resolution."),
            ],
        ),
    ]


def find_node_by_id(nodes: list[StoryNode], node_id: str) -> StoryNode | None:
    for node in nodes:
        if node.id == node_id:
            return node
        match = find_node_by_id(node.children, node_id)
        if match is not None:
            return match
    return None
