#!/usr/bin/env python3
"""
POC: Graph Population — NetworkXGraphStore + queries for BPMN/RACI views.

TASK-003: Загрузить артефакты из fixture, построить граф, выполнить
query_process() и query_raci(), сравнить с существующим output.

Использование:
    python3 poc/poc_graph_population.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.knowledge_types import KnowledgeArtifact, KnowledgeType, Provenance
from core.edge_types import EdgeType


RACI_EDGE_TYPES = {
    EdgeType.RESPONSIBLE_FOR.value,
    EdgeType.ACCOUNTABLE_FOR.value,
    EdgeType.CONSULTED_IN.value,
    EdgeType.INFORMED_OF.value,
}

RACI_LABELS = {
    EdgeType.RESPONSIBLE_FOR.value: "R",
    EdgeType.ACCOUNTABLE_FOR.value: "A",
    EdgeType.CONSULTED_IN.value: "C",
    EdgeType.INFORMED_OF.value: "I",
}

FLOW_EDGE_TYPES = {
    EdgeType.SEQUENCE.value,
    EdgeType.DECISION.value,
    EdgeType.PARALLEL.value,
}


class NetworkXGraphStore:
    """MVP implementation of GraphStore Protocol using NetworkX."""

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()

    def add_artifact(self, artifact: KnowledgeArtifact) -> str:
        self._graph.add_node(
            artifact.id,
            type=artifact.type.value if isinstance(artifact.type, KnowledgeType) else artifact.type,
            content=artifact.content,
            provenance={
                "document_code": artifact.provenance.document_code,
                "document_version": artifact.provenance.document_version,
                "section": artifact.provenance.section,
                "page": artifact.provenance.page,
                "paragraph": artifact.provenance.paragraph,
                "document_authority": artifact.provenance.document_authority,
                "extraction_method": artifact.provenance.extraction_method,
                "confidence": artifact.provenance.confidence,
            },
        )
        return artifact.id

    def add_relation(
        self,
        source: str,
        target: str,
        rel_type: str,
        props: dict | None = None,
    ) -> None:
        self._graph.add_edge(source, target, rel_type=rel_type, **(props or {}))

    def delete_by_document(self, doc_code: str) -> None:
        to_remove = [
            n for n, d in self._graph.nodes(data=True)
            if d.get("provenance", {}).get("document_code") == doc_code
        ]
        self._graph.remove_nodes_from(to_remove)

    def query_neighbors(
        self,
        node_id: str,
        hops: int = 1,
        edge_types: list[str] | None = None,
    ) -> list[dict]:
        if node_id not in self._graph:
            return []
        result = []
        visited = {node_id}
        frontier = {node_id}
        for _ in range(hops):
            next_frontier = set()
            for n in frontier:
                for _, nbr, data in self._graph.edges(n, data=True):
                    if edge_types and data.get("rel_type") not in edge_types:
                        continue
                    if nbr not in visited:
                        visited.add(nbr)
                        next_frontier.add(nbr)
                        result.append({
                            "id": nbr,
                            **self._graph.nodes[nbr],
                            "_edge": data,
                        })
                for pred, _, data in self._graph.in_edges(n, data=True):
                    if edge_types and data.get("rel_type") not in edge_types:
                        continue
                    if pred not in visited:
                        visited.add(pred)
                        next_frontier.add(pred)
                        result.append({
                            "id": pred,
                            **self._graph.nodes[pred],
                            "_edge": data,
                        })
            frontier = next_frontier
        return result

    def query_by_type(self, artifact_type: KnowledgeType) -> list[dict]:
        type_val = artifact_type.value if isinstance(artifact_type, KnowledgeType) else artifact_type
        return [
            {"id": n, **d}
            for n, d in self._graph.nodes(data=True)
            if d.get("type") == type_val
        ]

    def query_by_document(self, doc_code: str) -> list[dict]:
        return [
            {"id": n, **d}
            for n, d in self._graph.nodes(data=True)
            if d.get("provenance", {}).get("document_code") == doc_code
        ]

    def query_process(self, doc_code: str) -> dict:
        """Roles, steps, decisions, flows for BPMN rendering."""
        nodes = self.query_by_document(doc_code)

        roles = [n for n in nodes if n["type"] == KnowledgeType.ROLE.value]
        steps = [n for n in nodes if n["type"] == KnowledgeType.PROCESS_STEP.value]
        decisions = [n for n in nodes if n["type"] == KnowledgeType.DECISION_RULE.value]
        io_nodes = [n for n in nodes if n["type"] == KnowledgeType.INPUT_OUTPUT.value]

        flows = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("rel_type") in FLOW_EDGE_TYPES:
                u_prov = self._graph.nodes[u].get("provenance", {})
                if u_prov.get("document_code") == doc_code:
                    flows.append({
                        "source": u,
                        "target": v,
                        "type": data["rel_type"],
                    })

        return {
            "doc_code": doc_code,
            "roles": roles,
            "steps": steps,
            "decisions": decisions,
            "io": io_nodes,
            "flows": flows,
        }

    def query_raci(self, doc_code: str) -> list[dict]:
        """Role x Step x RACI type matrix."""
        doc_nodes = {n["id"] for n in self.query_by_document(doc_code)}
        steps = [
            n for n, d in self._graph.nodes(data=True)
            if n in doc_nodes and d.get("type") == KnowledgeType.PROCESS_STEP.value
        ]
        roles = [
            n for n, d in self._graph.nodes(data=True)
            if n in doc_nodes and d.get("type") == KnowledgeType.ROLE.value
        ]

        matrix: list[dict] = []
        for step_id in steps:
            step_data = self._graph.nodes[step_id]
            row: dict = {
                "step_id": step_id,
                "step_name": step_data.get("content", {}).get("name", step_id),
            }
            for role_id in roles:
                raci_val = ""
                for _, tgt, data in self._graph.edges(role_id, data=True):
                    if tgt == step_id and data.get("rel_type") in RACI_EDGE_TYPES:
                        raci_val += RACI_LABELS.get(data["rel_type"], "?")
                row[role_id] = raci_val
            matrix.append(row)
        return matrix

    def query_kpi(self, org_unit: str | None = None) -> list[dict]:
        kpis = self.query_by_type(KnowledgeType.KPI)
        if org_unit:
            kpis = [k for k in kpis if k.get("content", {}).get("owner_role") == org_unit]
        return kpis

    def query_controls(self, scope: str | None = None) -> list[dict]:
        return self.query_by_type(KnowledgeType.CONTROL)

    def query_for_rag(
        self,
        entities: list[str],
        edge_types: list[str] | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        results = []
        for entity in entities:
            results.extend(self.query_neighbors(entity, hops=max_hops, edge_types=edge_types))
        return results

    def save(self, path: str) -> None:
        data = nx.node_link_data(self._graph, edges="edges")
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._graph = nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()


def load_fixture(fixture_path: Path) -> tuple[list[KnowledgeArtifact], list[dict]]:
    """Load artifacts and relations from JSON fixture."""
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    artifacts = []
    for a in raw["artifacts"]:
        prov_data = a["provenance"]
        prov = Provenance(
            document_code=prov_data["document_code"],
            document_version=prov_data["document_version"],
            section=prov_data["section"],
            page=prov_data["page"],
            paragraph=prov_data.get("paragraph"),
            document_authority=prov_data.get("document_authority", "canonical"),
            extraction_method=prov_data.get("extraction_method", ""),
            confidence=prov_data.get("confidence", 1.0),
        )
        artifact = KnowledgeArtifact(
            id=a["id"],
            type=KnowledgeType(a["type"]),
            content=a["content"],
            provenance=prov,
        )
        artifacts.append(artifact)

    relations = raw.get("relations", [])
    return artifacts, relations


def print_raci_table(matrix: list[dict], roles: list[dict]) -> None:
    """Print RACI matrix as formatted table."""
    role_ids = [r["id"] for r in roles]
    role_names = {r["id"]: r["content"]["name"] for r in roles}

    header = f"{'Задача':<45}"
    for rid in role_ids:
        name = role_names[rid]
        short = name[:18]
        header += f" {short:<18}"
    print(header)
    print("-" * len(header))

    for row in matrix:
        line = f"{row['step_name'][:44]:<45}"
        for rid in role_ids:
            val = row.get(rid, "")
            line += f" {val:<18}"
        print(line)


def main() -> None:
    fixture_path = PROJECT_ROOT / "poc" / "fixtures" / "kd_rg_039_05_artifacts.json"
    if not fixture_path.exists():
        print(f"ERROR: Fixture not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    print("=== TASK-003: POC Graph Population ===\n")

    # --- 1. Load fixture ---
    artifacts, relations = load_fixture(fixture_path)
    print(f"Loaded: {len(artifacts)} artifacts, {len(relations)} relations")

    # --- 2. Populate graph ---
    store = NetworkXGraphStore()
    for a in artifacts:
        store.add_artifact(a)
    for r in relations:
        store.add_relation(r["source"], r["target"], r["type"], r.get("props"))

    print(f"Graph: {store.node_count} nodes, {store.edge_count} edges\n")

    # --- 3. query_process ---
    doc_code = "КД-РГ-039-05"
    process = store.query_process(doc_code)
    print(f"=== query_process('{doc_code}') ===")
    print(f"  Roles:     {len(process['roles'])}")
    print(f"  Steps:     {len(process['steps'])}")
    print(f"  Decisions: {len(process['decisions'])}")
    print(f"  I/O:       {len(process['io'])}")
    print(f"  Flows:     {len(process['flows'])}")

    print("\n  Roles:")
    for r in process["roles"]:
        print(f"    - {r['content']['name']} ({r['id']})")

    print("\n  Steps (sequence):")
    for s in process["steps"]:
        print(f"    - {s['content']['name']} [{s['content'].get('performer_role', '?')}]")

    print("\n  Decisions:")
    for d in process["decisions"]:
        print(f"    - {d['content']['condition']}")
        print(f"      → TRUE:  {d['content']['if_true']}")
        print(f"      → FALSE: {d['content']['if_false']}")

    print("\n  Flows:")
    for f in process["flows"]:
        print(f"    {f['source']} --[{f['type']}]--> {f['target']}")

    # --- 4. query_raci ---
    print(f"\n=== query_raci('{doc_code}') ===\n")
    raci_matrix = store.query_raci(doc_code)
    print_raci_table(raci_matrix, process["roles"])

    # --- 5. Compare with existing RACI ---
    existing_raci_path = PROJECT_ROOT / "output" / "КД-РГ-039-05" / "КД-РГ-039-05_RACI.md"
    if existing_raci_path.exists():
        print(f"\n=== Сравнение с существующим RACI ===")
        print(f"  Файл: {existing_raci_path.name}")
        existing_text = existing_raci_path.read_text(encoding="utf-8")

        match_count = 0
        total_count = 0
        for row in raci_matrix:
            step_name = row["step_name"]
            for role in process["roles"]:
                rid = role["id"]
                raci_val = row.get(rid, "")
                if raci_val:
                    total_count += 1
                    role_name = role["content"]["name"]
                    found_in_existing = False
                    for line in existing_text.split("\n"):
                        if step_name[:20] in line and f"| {raci_val} |" in line:
                            found_in_existing = True
                            break
                    if found_in_existing:
                        match_count += 1

        if total_count > 0:
            accuracy = match_count / total_count * 100
            print(f"  Совпадений: {match_count}/{total_count} ({accuracy:.0f}%)")
            print(f"  Порог: 80%  →  {'PASS' if accuracy >= 80 else 'FAIL'}")
        else:
            print("  Нет данных для сравнения")
    else:
        print(f"\n  Существующий RACI не найден: {existing_raci_path}")

    # --- 6. Save/Load round-trip ---
    print(f"\n=== Save/Load round-trip ===")
    save_path = PROJECT_ROOT / "poc" / "graph_КД-РГ-039-05.json"
    store.save(str(save_path))
    print(f"  Saved: {save_path.name} ({save_path.stat().st_size} bytes)")

    store2 = NetworkXGraphStore()
    store2.load(str(save_path))
    print(f"  Loaded: {store2.node_count} nodes, {store2.edge_count} edges")

    nodes_match = store.node_count == store2.node_count
    edges_match = store.edge_count == store2.edge_count
    print(f"  Nodes match: {nodes_match}")
    print(f"  Edges match: {edges_match}")

    process2 = store2.query_process(doc_code)
    raci2 = store2.query_raci(doc_code)
    data_match = (
        len(process2["roles"]) == len(process["roles"])
        and len(process2["steps"]) == len(process["steps"])
        and len(raci2) == len(raci_matrix)
    )
    print(f"  Data match:  {data_match}")
    print(f"  Round-trip:  {'PASS' if nodes_match and edges_match and data_match else 'FAIL'}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print("ИТОГИ POC Graph Population:")
    print(f"  NetworkXGraphStore: 10 методов реализовано")
    print(f"  Fixture: {len(artifacts)} артефактов, {len(relations)} связей")
    print(f"  query_process: {len(process['roles'])} roles, {len(process['steps'])} steps, {len(process['flows'])} flows")
    print(f"  query_raci: {len(raci_matrix)} строк матрицы")
    print(f"  Round-trip: {'OK' if nodes_match and edges_match and data_match else 'FAIL'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
