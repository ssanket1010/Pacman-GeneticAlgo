"""Utilities for rendering genetic-algorithm lineage trees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LINEAGE_PATH = Path("outputs/ga_lineage.json")
DEFAULT_OUTPUT_PATH = Path("outputs/lineage_tree.svg")


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize supported lineage JSON shapes into a record list."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        records = payload.get("records") or payload.get("lineage") or payload.get("genomes")
        if isinstance(records, list):
            return records
    raise ValueError("Lineage JSON must be a list or an object containing a records list.")


def _node_label(record: dict[str, Any]) -> str:
    genome_id = record.get("genome_id", record.get("id", "?"))
    generation = record.get("generation", "?")
    fitness = record.get("fitness")
    if isinstance(fitness, (int, float)):
        fitness_text = f"{fitness:.1f}"
    elif fitness is None:
        fitness_text = "n/a"
    else:
        fitness_text = str(fitness)
    return f"Gen {generation}\n{genome_id}\nfit {fitness_text}"


def _mutation_text(record: dict[str, Any]) -> str:
    mutated = record.get("mutation_count", record.get("mutated_genes", 0))
    try:
        mutated_count = int(mutated)
    except (TypeError, ValueError):
        return f"mutated: {mutated}"
    if mutated_count <= 0:
        return ""
    noun = "gene" if mutated_count == 1 else "genes"
    return f"mutated: {mutated_count} {noun}"


def render_lineage_tree(
    lineage_path: str | Path = DEFAULT_LINEAGE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Render a GA lineage JSON file to a directed graph image.

    Parent genome IDs point to child genome IDs. Edge labels describe the genetic
    operation (selection/crossover/elite), and mutation counts are shown on the
    child node and appended to incoming edge labels.
    """
    lineage_path = Path(lineage_path)
    output_path = Path(output_path)

    with lineage_path.open("r", encoding="utf-8") as handle:
        records = _records_from_payload(json.load(handle))

    if output_path.suffix.lower() == ".svg":
        return _render_svg(records, output_path)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError as exc:  # pragma: no cover - depends on optional env deps
        raise RuntimeError(
            "Rendering PNG lineage trees requires networkx and matplotlib. "
            "Use an .svg output path or install them with: pip install networkx matplotlib"
        ) from exc

    graph = nx.DiGraph()
    edge_labels: dict[tuple[str, str], str] = {}
    mutated_nodes: set[str] = set()

    for record in records:
        genome_id = str(record.get("genome_id", record.get("id")))
        if genome_id in ("None", ""):
            continue
        mutation_text = _mutation_text(record)
        if mutation_text:
            mutated_nodes.add(genome_id)
        label = _node_label(record)
        if mutation_text:
            label = f"{label}\n{mutation_text}"
        graph.add_node(genome_id, label=label, generation=record.get("generation", 0))

    for record in records:
        child_id = str(record.get("genome_id", record.get("id")))
        if child_id not in graph:
            continue
        parent_ids = record.get("parent_ids", record.get("parents", [])) or []
        if isinstance(parent_ids, (str, int)):
            parent_ids = [parent_ids]
        operation = record.get("operation", record.get("event", "selection"))
        mutation_text = _mutation_text(record)
        edge_label = str(operation)
        if mutation_text:
            edge_label = f"{edge_label}\n{mutation_text}"
        for parent_id in parent_ids:
            parent_id = str(parent_id)
            if parent_id not in graph:
                graph.add_node(parent_id, label=parent_id, generation=0)
            graph.add_edge(parent_id, child_id)
            edge_labels[(parent_id, child_id)] = edge_label

    if not graph.nodes:
        raise ValueError(f"No lineage records found in {lineage_path}")

    generations = nx.get_node_attributes(graph, "generation")
    try:
        pos = nx.multipartite_layout(graph, subset_key="generation")
    except Exception:
        pos = nx.spring_layout(graph, seed=7)

    node_colors = ["#ffcc66" if node in mutated_nodes else "#9ecae1" for node in graph.nodes]
    width = max(8, min(24, len(graph.nodes) * 0.45))
    height = max(6, min(18, len(set(generations.values())) * 2.2 + 3))

    plt.figure(figsize=(width, height))
    nx.draw_networkx_edges(graph, pos, arrows=True, arrowstyle="-|>", arrowsize=16, edge_color="#555555")
    nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=2100, edgecolors="#333333")
    nx.draw_networkx_labels(graph, pos, labels=nx.get_node_attributes(graph, "label"), font_size=8)
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=7, label_pos=0.55)
    plt.title("GA Lineage Tree")
    plt.axis("off")
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()
    return output_path


def _render_svg(records: list[dict[str, Any]], output_path: Path) -> Path:
    """Render a dependency-free SVG lineage tree."""
    from html import escape

    nodes = {}
    edges = []
    for record in records:
        genome_id = str(record.get("genome_id", record.get("id")))
        if genome_id in ("None", ""):
            continue
        nodes[genome_id] = record
    for record in records:
        child_id = str(record.get("genome_id", record.get("id")))
        parent_ids = record.get("parent_ids", record.get("parents", [])) or []
        if isinstance(parent_ids, (str, int)):
            parent_ids = [parent_ids]
        for parent_id in parent_ids:
            edges.append((str(parent_id), child_id, record))
            nodes.setdefault(str(parent_id), {"genome_id": str(parent_id), "generation": 0})

    if not nodes:
        raise ValueError("No lineage records found to render")

    generations: dict[int, list[str]] = {}
    for genome_id, record in nodes.items():
        try:
            generation = int(record.get("generation", 0))
        except (TypeError, ValueError):
            generation = 0
        generations.setdefault(generation, []).append(genome_id)

    x_gap = 220
    y_gap = 110
    margin = 70
    max_rows = max(len(ids) for ids in generations.values())
    width = max(500, margin * 2 + (max(generations) + 1) * x_gap)
    height = max(300, margin * 2 + max_rows * y_gap)
    positions = {}
    for generation, ids in sorted(generations.items()):
        ids.sort()
        column_height = (len(ids) - 1) * y_gap
        top = (height - column_height) / 2
        for row, genome_id in enumerate(ids):
            positions[genome_id] = (margin + generation * x_gap, top + row * y_gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#555" /></marker></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="30" font-size="22" font-family="Arial" font-weight="bold">GA Lineage Tree</text>',
    ]
    for parent_id, child_id, record in edges:
        if parent_id not in positions or child_id not in positions:
            continue
        x1, y1 = positions[parent_id]
        x2, y2 = positions[child_id]
        label = str(record.get("operation", "selection"))
        mutation_text = _mutation_text(record)
        if mutation_text:
            label = f"{label}; {mutation_text}"
        parts.append(f'<line x1="{x1 + 70}" y1="{y1}" x2="{x2 - 70}" y2="{y2}" stroke="#555" stroke-width="1.5" marker-end="url(#arrow)"/>')
        parts.append(f'<text x="{(x1+x2)/2 - 45}" y="{(y1+y2)/2 - 6}" font-size="11" font-family="Arial" fill="#333">{escape(label)}</text>')
    for genome_id, record in nodes.items():
        x, y = positions[genome_id]
        mutation_text = _mutation_text(record)
        fill = "#ffcc66" if mutation_text else "#9ecae1"
        parts.append(f'<rect x="{x-72}" y="{y-34}" width="144" height="68" rx="10" fill="{fill}" stroke="#333"/>')
        for idx, line in enumerate(_node_label(record).split("\n") + ([mutation_text] if mutation_text else [])):
            parts.append(f'<text x="{x}" y="{y - 17 + idx * 15}" text-anchor="middle" font-size="12" font-family="Arial">{escape(line)}</text>')
    parts.append('</svg>')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path
