"""
AgentNode: kapselt ein OR-Set als lokales Replikat eines geteilten
Task-Ledgers und simuliert einen unabhaengig arbeitenden Agenten in einem
Multi-Agent-System - ohne zentrale Koordinationsinstanz.
"""

from __future__ import annotations

from crdt_ledger.or_set import ORSet


class AgentNode:
    """
    Ein autonomer Knoten, der eine lokale Kopie einer geteilten Aufgaben-
    liste haelt und unabhaengig von anderen Knoten Aufgaben hinzufuegen
    oder abschliessen kann - auch 'offline', ohne dass irgendeine zentrale
    Instanz die Reihenfolge oder Gueltigkeit von Operationen entscheidet.
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.ledger: ORSet[str] = ORSet(node_id)

    def add_task(self, description: str) -> None:
        self.ledger.add(description)

    def complete_task(self, description: str) -> None:
        self.ledger.remove(description)

    def active_tasks(self) -> set[str]:
        return self.ledger.values()

    def sync_with(self, other: "AgentNode") -> None:
        """
        Bidirektionale Synchronisation zweier Knoten.

        Beide Seiten werden unabhaengig mit merge() aktualisiert. Da merge()
        kommutativ ist (bewiesen in tests/test_or_set.py), landen beide
        Knoten garantiert im selben Zustand - unabhaengig davon, wie oft
        oder in welcher Reihenfolge sync_with() zwischen beliebigen
        Knotenpaaren im Netzwerk aufgerufen wird.
        """
        merged_self = self.ledger.merge(other.ledger)
        merged_other = other.ledger.merge(self.ledger)
        self.ledger = merged_self
        other.ledger = merged_other

    def __repr__(self) -> str:
        return f"AgentNode({self.node_id!r}, active={sorted(self.active_tasks())!r})"
