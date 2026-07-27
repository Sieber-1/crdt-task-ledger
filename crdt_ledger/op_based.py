"""
Operation-based OR-Set (CmRDT) - Gegenstueck zu or_set.py (state-based, CvRDT).

STATE-BASED (or_set.py): Replikate tauschen ihren VOLLSTAENDIGEN Zustand aus.
merge() muss kommutativ/assoziativ/idempotent sein. Uebertragung darf
beliebig oft wiederholt werden und in beliebiger Reihenfolge ankommen
("at-least-once", "any order").

OPERATION-BASED (dieses Modul): Replikate tauschen nur einzelne Operationen
aus (Add/Remove), nicht den ganzen Zustand - deutlich weniger Bandbreite bei
vielen kleinen Aenderungen. Dafuer andere Anforderungen an die Zustellung:

1. KAUSALE REIHENFOLGE fuer abhaengige Operationen: ein Remove(tag) darf bei
   einem Replikat erst wirken, NACHDEM das zugehoerige Add(value, tag) dort
   bereits angewendet wurde - sonst weiss das Replikat nicht, worauf sich
   der Tag ueberhaupt bezieht. Dieses Modul loest das mit einer expliziten
   Pending-Queue: ein zu frueh eintreffendes Remove wird zurueckgehalten,
   bis sein Add angekommen ist (siehe _apply_remove).

2. Nebenlaeufige (kausal unabhaengige) Operationen brauchen dagegen KEINE
   bestimmte Reihenfolge - zwei unabhaengige Add()-Operationen auf
   verschiedenen Replikaten duerfen in beliebiger Reihenfolge eintreffen.

Interessante Randnotiz, die man beim genauen Hinsehen merkt: klassische
Lehrbuch-CmRDTs fordern oft "exactly-once"-Zustellung, weil viele Operationen
(z.B. ein Counter-Increment) bei doppelter Anwendung falsche Ergebnisse
liefern. Beim OR-Set ist das nicht zwingend - jede Operation trägt einen
global eindeutigen Tag, wodurch add()/remove() auf Mengen-Ebene von Natur
aus idempotent sind (zweimaliges Hinzufuegen desselben (value,tag)-Paares
aendert nichts). Die Deduplizierung per _applied_op_ids ist hier also eher
Demonstration der allgemeinen CmRDT-Praxis als eine Notwendigkeit fuer
Korrektheit bei GENAU DIESER Datenstruktur - ein Punkt, der leicht uebersehen
wird, wenn man das Muster nur aus dem Lehrbuch uebernimmt statt es zu Ende
zu durchdenken.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from crdt_ledger.or_set import Tag


@dataclass(frozen=True)
class AddOp:
    value: Any
    tag: Tag

    @property
    def op_id(self) -> str:
        return f"add:{self.tag.node_id}:{self.tag.op_id}"


@dataclass(frozen=True)
class RemoveOp:
    tag: Tag

    @property
    def op_id(self) -> str:
        return f"remove:{self.tag.node_id}:{self.tag.op_id}"


Op = Union[AddOp, RemoveOp]


class OpBasedORSet:
    """Operation-based OR-Set: Zustandsaenderung durch Anwenden einzelner
    Add-/Remove-Operationen statt durch Zusammenfuehren vollstaendiger Zustaende."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._adds: set[tuple[Any, Tag]] = set()
        self._removes: set[Tag] = set()
        self._pending_removes: set[Tag] = set()  # Removes, deren Add noch fehlt
        self._applied_op_ids: set[str] = set()  # Dedup-Schutz (siehe Modul-Docstring)

    # --- Lokale Operationen: erzeugen UND wenden sofort lokal an ---

    def add(self, value: Any) -> AddOp:
        """Erzeugt eine neue Add-Operation, wendet sie lokal an, gibt sie
        zum Broadcasten an andere Replikate zurueck."""
        tag = Tag.new(self.node_id)
        op = AddOp(value, tag)
        self._apply_add(op)
        self._applied_op_ids.add(op.op_id)
        return op

    def remove(self, value: Any) -> list[RemoveOp]:
        """Erzeugt fuer jeden aktuell sichtbaren Tag von `value` eine
        Remove-Operation, wendet jede lokal an, gibt sie zum Broadcasten zurueck."""
        ops: list[RemoveOp] = []
        for v, tag in list(self._adds):
            if v == value and tag not in self._removes:
                op = RemoveOp(tag)
                self._apply_remove(op)
                self._applied_op_ids.add(op.op_id)
                ops.append(op)
        return ops

    # --- Remote-Operationen: von einem anderen Replikat empfangen ---

    def apply_remote(self, op: Op) -> None:
        """Wendet eine von einem anderen Replikat empfangene Operation an."""
        if op.op_id in self._applied_op_ids:
            return  # Duplikat - bereits angewendet
        self._applied_op_ids.add(op.op_id)

        if isinstance(op, AddOp):
            self._apply_add(op)
        elif isinstance(op, RemoveOp):
            self._apply_remove(op)

    # --- Interne Anwendung (gemeinsam fuer lokale und Remote-Operationen) ---

    def _apply_add(self, op: AddOp) -> None:
        self._adds.add((op.value, op.tag))
        # Falls ein frueher eingetroffenes Remove auf dieses Tag gewartet hat:
        if op.tag in self._pending_removes:
            self._pending_removes.discard(op.tag)
            self._removes.add(op.tag)

    def _apply_remove(self, op: RemoveOp) -> None:
        tag_known = any(t == op.tag for _, t in self._adds)
        if tag_known:
            self._removes.add(op.tag)
        else:
            # Kausale Abhaengigkeit (das zugehoerige Add) noch nicht erfuellt.
            # Zurueckstellen statt falsch anzuwenden oder zu verwerfen.
            self._pending_removes.add(op.tag)

    # --- Abfragen ---

    def values(self) -> set[Any]:
        return {v for v, tag in self._adds if tag not in self._removes}

    def __contains__(self, value: Any) -> bool:
        return value in self.values()

    def __repr__(self) -> str:
        return f"OpBasedORSet(node={self.node_id!r}, values={self.values()!r})"
