"""
Integrationstest: echte Konvergenz ueber einen echten NATS-Message-Broker,
nicht simuliert innerhalb eines Prozesses.

Dieser Test benoetigt einen laufenden NATS-Server (nats-server -p 4222).
Falls keiner erreichbar ist, wird der Test uebersprungen (skip), damit die
Kern-Testsuite (test_or_set.py, test_convergence.py, test_node.py) auch
ohne NATS-Installation vollstaendig laeuft.

Ausfuehren (mit laufendem NATS-Server):
    nats-server -p 4222 &
    pytest tests/test_broker_integration.py -v
"""

import asyncio
import socket

import pytest

from crdt_ledger.broker import NetworkedAgentNode


def _nats_reachable(host: str = "localhost", port: int = 4222) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


requires_nats = pytest.mark.skipif(
    not _nats_reachable(),
    reason="Kein NATS-Server auf localhost:4222 erreichbar - "
    "starte 'nats-server -p 4222' um diesen Test auszufuehren.",
)


@requires_nats
@pytest.mark.asyncio
async def test_three_nodes_converge_over_real_nats():
    """
    Drei Knoten, drei getrennte NATS-Client-Verbindungen, echte Netzwerk-
    Nachrichten (kein direkter Methodenaufruf wie bei AgentNode.sync_with).
    Nach kurzer Wartezeit fuer die Propagation muessen alle drei denselben
    Zustand haben.
    """
    alice = NetworkedAgentNode("alice-it")
    bob = NetworkedAgentNode("bob-it")
    carol = NetworkedAgentNode("carol-it")

    try:
        await alice.connect()
        await bob.connect()
        await carol.connect()
        await asyncio.sleep(0.3)  # Subscriptions beim Server aktivieren lassen

        await alice.add_task("Rechnung pruefen")
        await bob.add_task("Angebot erstellen")
        await carol.add_task("Meeting vorbereiten")
        await asyncio.sleep(0.5)  # Propagationszeit ueber den Broker

        expected = {"Rechnung pruefen", "Angebot erstellen", "Meeting vorbereiten"}
        assert alice.active_tasks() == expected
        assert bob.active_tasks() == expected
        assert carol.active_tasks() == expected
    finally:
        await alice.close()
        await bob.close()
        await carol.close()


@requires_nats
@pytest.mark.asyncio
async def test_concurrent_add_remove_over_real_nats_add_wins():
    """
    Die entscheidende CRDT-Eigenschaft (siehe test_node.py), hier aber ueber
    echte Netzwerk-Propagation statt direktem sync_with() geprueft.
    """
    alice = NetworkedAgentNode("alice-cr")
    carol = NetworkedAgentNode("carol-cr")

    try:
        await alice.connect()
        await carol.connect()
        await asyncio.sleep(0.3)

        await carol.add_task("Rechnung pruefen")
        await carol.complete_task("Rechnung pruefen")  # Carol: erledigt

        await alice.add_task("Rechnung pruefen")  # Alice: unabhaengig neu angelegt
        await asyncio.sleep(0.5)

        assert "Rechnung pruefen" in alice.active_tasks()
        assert "Rechnung pruefen" in carol.active_tasks()
    finally:
        await alice.close()
        await carol.close()
