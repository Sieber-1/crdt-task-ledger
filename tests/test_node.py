"""
Tests fuer AgentNode: die Anwendungsschicht ueber dem OR-Set, die einen
unabhaengig arbeitenden Agenten mit einer geteilten Aufgabenliste simuliert.

Ausfuehren: pytest tests/test_node.py -v
"""

from crdt_ledger.node import AgentNode


def test_node_starts_empty():
    n = AgentNode("n1")
    assert n.active_tasks() == set()


def test_add_and_complete_task():
    n = AgentNode("n1")
    n.add_task("Rechnung pruefen")
    assert "Rechnung pruefen" in n.active_tasks()
    n.complete_task("Rechnung pruefen")
    assert "Rechnung pruefen" not in n.active_tasks()


def test_sync_converges_two_nodes():
    alice = AgentNode("alice")
    bob = AgentNode("bob")
    alice.add_task("Angebot pruefen")
    bob.add_task("Meeting vorbereiten")

    alice.sync_with(bob)

    assert alice.active_tasks() == bob.active_tasks()
    assert alice.active_tasks() == {"Angebot pruefen", "Meeting vorbereiten"}


def test_concurrent_add_survives_independent_remove():
    """
    Die entscheidende Eigenschaft fuer 'Koordination ohne zentrale Kontrolle':
    Carol entfernt eine Aufgabe, die sie selbst (unabhaengig) angelegt hatte -
    aus ihrer Sicht ist die Aufgabe erledigt. Alice legt DIESELBE Aufgabe
    unabhaengig neu an, ohne von Carols Zustand zu wissen. Nach der
    Synchronisation muss die Aufgabe als aktiv gelten - Alices Information
    war unabhaengig und darf durch Carols fruehere, unwissende Entfernung
    nicht verloren gehen.
    """
    alice = AgentNode("alice")
    carol = AgentNode("carol")

    carol.add_task("Rechnung pruefen")
    carol.complete_task("Rechnung pruefen")  # Carol denkt: erledigt

    alice.add_task("Rechnung pruefen")  # Alice, unabhaengig, legt sie neu an

    alice.sync_with(carol)

    assert "Rechnung pruefen" in alice.active_tasks()
    assert "Rechnung pruefen" in carol.active_tasks()


def test_three_way_sync_converges_regardless_of_order():
    alice = AgentNode("alice")
    bob = AgentNode("bob")
    carol = AgentNode("carol")

    alice.add_task("A")
    bob.add_task("B")
    carol.add_task("C")

    bob.sync_with(carol)
    alice.sync_with(bob)
    carol.sync_with(alice)

    assert alice.active_tasks() == bob.active_tasks() == carol.active_tasks()
    assert alice.active_tasks() == {"A", "B", "C"}


def test_offline_work_then_late_sync_still_converges():
    """Simuliert laengere Offline-Phasen: viele Operationen vor dem ersten Sync."""
    alice = AgentNode("alice")
    bob = AgentNode("bob")

    for i in range(10):
        alice.add_task(f"alice-task-{i}")
    for i in range(10):
        bob.add_task(f"bob-task-{i}")
    alice.complete_task("alice-task-3")
    bob.complete_task("bob-task-7")

    alice.sync_with(bob)

    expected = {f"alice-task-{i}" for i in range(10) if i != 3} | {
        f"bob-task-{i}" for i in range(10) if i != 7
    }
    assert alice.active_tasks() == expected
    assert bob.active_tasks() == expected
