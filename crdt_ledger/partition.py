"""
Simulation von Netzwerk-Partitionen: Gruppen von Agent-Knoten, die sich
zeitweise nicht erreichen koennen, aber unabhaengig weiterarbeiten - und
nach dem Heilen der Partition garantiert wieder konvergieren.

Das ist der Kernfall, den echte "unabhaengig evolvierende, verteilte
Systeme" (siehe Aufgabenstellung: 'reliably across distributed,
independently evolving systems') beherrschen muessen: eine Partition ist
kein Fehlerfall, den man verhindern kann - sie IST der Normalfall in
verteilten Systemen (Netzwerkausfall, getrennte Rechenzentren, Knoten
temporaer offline). Ein CRDT macht daraus kein Problem, weil Knoten
waehrend der Partition einfach unabhaengig weiterarbeiten und die
Konvergenz-Garantie beim Wiederzusammenfuehren automatisch greift.
"""

from __future__ import annotations

from crdt_ledger.node import AgentNode


class PartitionedNetwork:
    """
    Verwaltet eine Menge von AgentNode-Instanzen mit konfigurierbaren
    Netzwerk-Partitionen. Waehrend eine Partition aktiv ist, koennen nur
    Knoten INNERHALB derselben Gruppe synchronisieren - Knoten in
    unterschiedlichen Gruppen sehen sich gegenseitig nicht.
    """

    def __init__(self, nodes: list[AgentNode]):
        self.nodes: dict[str, AgentNode] = {n.node_id: n for n in nodes}
        self._groups: list[set[str]] | None = None  # None = keine Partition aktiv

    def partition(self, *groups: list[str]) -> None:
        """
        Teilt das Netzwerk in isolierte Gruppen auf.

        Beispiel: partition(["alice", "bob"], ["carol", "dave"]) trennt das
        Netzwerk in zwei Haelften, die sich gegenseitig nicht erreichen.
        """
        all_ids = {n_id for g in groups for n_id in g}
        unknown = all_ids - set(self.nodes.keys())
        if unknown:
            raise ValueError(f"Unbekannte Knoten-IDs in Partition: {unknown}")
        self._groups = [set(g) for g in groups]

    def heal(self) -> None:
        """Hebt jede aktive Partition auf - alle Knoten koennen sich wieder erreichen."""
        self._groups = None

    def can_reach(self, node_a_id: str, node_b_id: str) -> bool:
        """Pruef, ob zwei Knoten sich beim aktuellen Partitions-Zustand erreichen koennen."""
        if self._groups is None:
            return True
        return any(node_a_id in g and node_b_id in g for g in self._groups)

    def try_sync(self, node_a_id: str, node_b_id: str) -> bool:
        """
        Versucht, zwei Knoten zu synchronisieren.

        Gibt False zurueck (und tut nichts), falls die beiden Knoten durch
        eine aktive Partition getrennt sind - genau wie ein echter
        Netzwerkausfall die Uebertragung verhindern wuerde.
        """
        if not self.can_reach(node_a_id, node_b_id):
            return False
        self.nodes[node_a_id].sync_with(self.nodes[node_b_id])
        return True

    def sync_all_reachable(self) -> None:
        """Synchronisiert alle Knotenpaare, die sich beim aktuellen Partitions-
        Zustand erreichen koennen - simuliert eine vollstaendige Gossip-Runde."""
        ids = list(self.nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                self.try_sync(ids[i], ids[j])

    def all_converged(self) -> bool:
        """Prueft, ob alle verwalteten Knoten denselben Zustand haben."""
        states = [n.active_tasks() for n in self.nodes.values()]
        return all(s == states[0] for s in states)
