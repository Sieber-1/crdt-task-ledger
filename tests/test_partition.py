"""
Tests fuer Netzwerk-Partitions-Toleranz: Gruppen von Knoten, die sich
zeitweise nicht erreichen, arbeiten unabhaengig weiter und konvergieren
nach dem Heilen garantiert - unabhaengig davon, was waehrend der Trennung
auf beiden Seiten passiert ist.

Ausfuehren: pytest tests/test_partition.py -v
"""

from crdt_ledger.node import AgentNode
from crdt_ledger.partition import PartitionedNetwork


def _make_five_nodes() -> list[AgentNode]:
    return [AgentNode(n) for n in ["alice", "bob", "carol", "dave", "erin"]]


def test_partition_blocks_cross_group_sync():
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])

    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    assert net.can_reach("alice", "bob") is True
    assert net.can_reach("carol", "dave") is True
    assert net.can_reach("alice", "carol") is False
    assert net.can_reach("bob", "erin") is False


def test_try_sync_fails_across_partition():
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    alice.add_task("nur alice")
    carol.add_task("nur carol")

    result = net.try_sync("alice", "carol")

    assert result is False, "Sync ueber eine Partitionsgrenze muss fehlschlagen"
    assert "nur carol" not in alice.active_tasks()
    assert "nur alice" not in carol.active_tasks()


def test_nodes_within_same_group_still_sync_during_partition():
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    alice.add_task("Angebot A")
    bob.add_task("Angebot B")

    ok = net.try_sync("alice", "bob")

    assert ok is True
    assert alice.active_tasks() == bob.active_tasks() == {"Angebot A", "Angebot B"}


def test_both_sides_work_independently_during_partition():
    """
    Der eigentliche Kernfall: waehrend der Partition arbeiten BEIDE Seiten
    unabhaengig weiter - keine Seite blockiert oder wartet auf die andere.
    """
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    for i in range(5):
        alice.add_task(f"alice-seite-{i}")
    for i in range(5):
        carol.add_task(f"carol-seite-{i}")

    net.sync_all_reachable()

    # Alice-Seite kennt nur ihre eigenen 5 Aufgaben
    assert len(alice.active_tasks()) == 5
    assert all(t.startswith("alice-seite") for t in alice.active_tasks())
    # Carol-Seite kennt nur ihre eigenen 5 Aufgaben
    assert len(carol.active_tasks()) == 5
    assert all(t.startswith("carol-seite") for t in carol.active_tasks())
    # Waehrend der Partition sind die Gruppen NICHT konvergiert
    assert net.all_converged() is False


def test_heal_restores_full_convergence():
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    alice.add_task("von der alice-Seite")
    carol.add_task("von der carol-Seite")
    net.sync_all_reachable()

    assert net.all_converged() is False  # noch getrennt

    net.heal()
    net.sync_all_reachable()

    assert net.all_converged() is True
    expected = {"von der alice-Seite", "von der carol-Seite"}
    assert alice.active_tasks() == expected
    assert erin.active_tasks() == expected  # auch ein Knoten der anderen Gruppe


def test_concurrent_conflicting_operations_across_partition_resolve_correctly():
    """
    Der anspruchsvollste Fall: WAEHREND der Partition legt eine Seite eine
    Aufgabe an, die andere Seite legt dieselbe Aufgabe an und entfernt sie
    wieder (aus ihrer eigenen, unabhaengigen Sicht erledigt). Nach dem
    Heilen muss trotzdem korrekt konvergiert werden - Add gewinnt gegen ein
    Remove, das es nie beobachtet hat, exakt wie im nicht-partitionierten Fall.
    """
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])

    alice.add_task("Rechnung pruefen")  # Alice-Seite: aktiv angelegt

    carol.add_task("Rechnung pruefen")  # Carol-Seite: unabhaengig angelegt...
    carol.complete_task("Rechnung pruefen")  # ...und sofort wieder als erledigt markiert
    net.sync_all_reachable()  # innerhalb der Gruppen synchronisieren

    net.heal()
    net.sync_all_reachable()

    assert net.all_converged() is True
    assert "Rechnung pruefen" in alice.active_tasks()
    assert "Rechnung pruefen" in erin.active_tasks()  # auch bei der Carol-Seite sichtbar


def test_repeated_partition_and_heal_cycles_still_converge():
    """Mehrere aufeinanderfolgende Partitionierungen/Heilungen - kein
    Zustand geht verloren, egal wie oft sich das Netzwerk auftrennt."""
    alice, bob, carol, dave, erin = _make_five_nodes()
    net = PartitionedNetwork([alice, bob, carol, dave, erin])

    # Runde 1: alice+bob getrennt von den anderen
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])
    alice.add_task("Runde1-alice")
    carol.add_task("Runde1-carol")
    net.sync_all_reachable()
    net.heal()
    net.sync_all_reachable()

    # Runde 2: andere Aufteilung
    net.partition(["alice", "carol"], ["bob", "dave", "erin"])
    dave.add_task("Runde2-dave")
    net.sync_all_reachable()
    net.heal()
    net.sync_all_reachable()

    assert net.all_converged() is True
    expected = {"Runde1-alice", "Runde1-carol", "Runde2-dave"}
    assert alice.active_tasks() == expected
    assert erin.active_tasks() == expected
