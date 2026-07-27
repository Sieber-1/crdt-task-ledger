"""
NATS-basierte asynchrone Propagation von OR-Set-Updates zwischen Agent-Knoten.

Im Gegensatz zu AgentNode.sync_with() (direkter, synchroner Methodenaufruf im
selben Prozess) laeuft die Kommunikation hier ueber einen echten Message-
Broker: jeder Knoten publiziert seinen OR-Set-Zustand auf ein gemeinsames
Subject und merged eingehende Updates automatisch in seinen lokalen Zustand.
Das demonstriert CRDT-Konvergenz ueber echte Netzwerk-/Prozessgrenzen hinweg,
nicht nur simuliert innerhalb eines einzelnen Python-Prozesses.

Design-Vereinfachung (bewusst, fuer Nachvollziehbarkeit): jeder Knoten
sendet bei jeder Aenderung seinen VOLLSTAENDIGEN lokalen Zustand, nicht nur
das Delta. Das ist wegen Idempotenz und Monotonie von merge() korrekt,
aber nicht bandbreitenoptimal - eine Produktivversion wuerde nur Deltas
uebertragen.

Benoetigt einen laufenden NATS-Server (https://nats.io):
    nats-server -p 4222
"""

from __future__ import annotations

import json
from typing import Optional

import nats
from nats.aio.client import Client as NATSClient

from crdt_ledger.or_set import ORSet, Tag

SUBJECT = "crdt.task_ledger.updates"


def _serialize(orset: "ORSet[str]") -> str:
    """Serialisiert den OR-Set-Zustand als JSON fuer die Uebertragung ueber NATS."""
    return json.dumps(
        {
            "node_id": orset.node_id,
            "adds": [[v, t.node_id, t.op_id] for v, t in orset._adds],
            "removes": [[t.node_id, t.op_id] for t in orset._removes],
        }
    )


def _deserialize(data: str) -> "ORSet[str]":
    """Rekonstruiert ein ORSet aus JSON, um es lokal zu mergen.

    Die node_id des Ergebnisses stammt aus der Nachricht selbst (wer hat
    gesendet), nicht vom Empfaenger - sonst wuerde der Echo-Filter in
    _on_message jede fremde Nachricht faelschlich als eigene erkennen.
    """
    payload = json.loads(data)
    result: ORSet[str] = ORSet(payload["node_id"])
    result._adds = {(v, Tag(node_id=n, op_id=o)) for v, n, o in payload["adds"]}
    result._removes = {Tag(node_id=n, op_id=o) for n, o in payload["removes"]}
    return result


class NetworkedAgentNode:
    """
    Wie AgentNode (siehe node.py), aber synchronisiert ueber einen echten
    NATS-Broker statt direkter Methodenaufrufe. Jede lokale Aenderung wird
    publiziert; jedes empfangene Update wird per merge() eingearbeitet.
    """

    def __init__(self, node_id: str, nats_url: str = "nats://localhost:4222") -> None:
        self.node_id = node_id
        self.nats_url = nats_url
        self.ledger: ORSet[str] = ORSet(node_id)
        self._nc: Optional[NATSClient] = None

    async def connect(self) -> None:
        self._nc = await nats.connect(self.nats_url)
        await self._nc.subscribe(SUBJECT, cb=self._on_message)

    async def _on_message(self, msg) -> None:
        remote = _deserialize(msg.data.decode())
        if remote.node_id != self.node_id:  # eigene Broadcasts ignorieren
            self.ledger = self.ledger.merge(remote)

    async def add_task(self, description: str) -> None:
        self.ledger.add(description)
        await self._publish()

    async def complete_task(self, description: str) -> None:
        self.ledger.remove(description)
        await self._publish()

    async def _publish(self) -> None:
        assert self._nc is not None, "connect() muss vor der ersten Aenderung aufgerufen werden"
        await self._nc.publish(SUBJECT, _serialize(self.ledger).encode())
        await self._nc.flush()

    def active_tasks(self) -> set:
        return self.ledger.values()

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.close()
