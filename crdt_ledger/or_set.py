"""
OR-Set (Observed-Remove Set) - eine CRDT (Conflict-free Replicated Data Type).

Kernproblem, das ein normales Set nicht loesen kann:
Zwei Knoten arbeiten unabhaengig (offline) an derselben Menge. Knoten A fuegt
"Task X" hinzu. Unabhaengig davon entfernt Knoten B "Task X" (das er von
einer frueheren eigenen Version kennt, aber Knoten A hat davon nie erfahren).
Wenn sich beide spaeter synchronisieren - wer gewinnt? Ein naives Set kann
das nicht widerspruchsfrei entscheiden, ohne eine zentrale Instanz zu fragen.

Die OR-Set-Loesung: jede add()-Operation bekommt eine eindeutige Marke (Tag).
remove() entfernt nur die Tags, die zum Zeitpunkt des Entfernens tatsaechlich
lokal beobachtet wurden ("observed"). Ein spaeter eintreffendes add() mit
neuem Tag ueberlebt ein aelteres remove() automatisch - "Add-Wins"-Semantik.

Die Merge-Operation ist reine Mengenvereinigung zweier interner Mengen -
dadurch beweisbar kommutativ, assoziativ und idempotent (Join-Semilattice).
Genau das macht CRDTs nuetzlich fuer Koordination ohne zentrale Kontrolle:
egal in welcher Reihenfolge oder wie oft Replikate zusammengefuehrt werden,
das Ergebnis konvergiert garantiert zum gleichen Zustand (Strong Eventual
Consistency).

Referenz: Shapiro, Preguica, Baquero, Zawirski - "Conflict-free Replicated
Data Types" (2011), Abschnitt zu Optimized OR-Sets.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Tag:
    """Eindeutige, unveraenderliche Marke fuer eine einzelne add()-Operation."""

    node_id: str
    op_id: str

    @staticmethod
    def new(node_id: str) -> "Tag":
        return Tag(node_id=node_id, op_id=uuid.uuid4().hex[:12])


class ORSet(Generic[T]):
    """
    Observed-Remove Set.

    Interner Zustand:
        _adds:    Menge von (value, Tag) Paaren - jede jemals ausgefuehrte add()
        _removes: Menge von Tags, die als entfernt markiert wurden (Tombstones)

    Invariante: ein Wert gilt als "im Set", wenn mindestens ein (value, tag)
    in _adds existiert, dessen tag NICHT in _removes enthalten ist.
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._adds: set[tuple[T, Tag]] = set()
        self._removes: set[Tag] = set()

    def add(self, value: T) -> None:
        """Fuegt value hinzu, mit einer frischen, eindeutigen Marke."""
        tag = Tag.new(self.node_id)
        self._adds.add((value, tag))

    def remove(self, value: T) -> None:
        """
        Entfernt value - aber nur die Tags, die JETZT lokal sichtbar sind.
        Ein add() das dieser Knoten noch nicht gesehen hat (weil es von einem
        anderen, noch nicht synchronisierten Knoten stammt), wird dadurch
        NICHT entfernt. Genau das ist die "Observed"-Eigenschaft.
        """
        for v, tag in self._adds:
            if v == value and tag not in self._removes:
                self._removes.add(tag)

    def __contains__(self, value: T) -> bool:
        return any(v == value and tag not in self._removes for v, tag in self._adds)

    def values(self) -> set[T]:
        """Alle aktuell 'lebendigen' Werte (mind. ein nicht entferntes Tag)."""
        return {v for v, tag in self._adds if tag not in self._removes}

    def merge(self, other: "ORSet[T]") -> "ORSet[T]":
        """
        Fuehrt diesen Zustand mit einem anderen Replikat zusammen.

        Reine Mengenvereinigung auf beiden internen Mengen - dadurch
        beweisbar kommutativ (merge(a,b) == merge(b,a)), assoziativ
        (Gruppierung egal) und idempotent (merge(a,a) == a). Diese drei
        Eigenschaften zusammen garantieren: unabhaengig davon, in welcher
        Reihenfolge oder wie oft merge() zwischen beliebigen Knoten
        aufgerufen wird, konvergieren alle Replikate zum selben Endzustand.
        """
        result: ORSet[T] = ORSet(self.node_id)
        result._adds = self._adds | other._adds
        result._removes = self._removes | other._removes
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ORSet):
            return NotImplemented
        return self._adds == other._adds and self._removes == other._removes

    def __repr__(self) -> str:
        return f"ORSet(node={self.node_id!r}, values={self.values()!r})"
