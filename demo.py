"""
Demo: 3 unabhaengige Agent-Knoten arbeiten 'offline' an einem geteilten
Task-Ledger, ohne zentrale Koordination - und konvergieren nach dem
Zusammenfuehren garantiert zum selben Zustand, unabhaengig von der
Synchronisations-Reihenfolge.

Ausfuehren: python demo.py
"""

from crdt_ledger.node import AgentNode


def print_state(nodes: list[AgentNode]) -> None:
    for n in nodes:
        print(f"  {n.node_id}: {sorted(n.active_tasks())}")


def main() -> None:
    alice = AgentNode("agent-alice")
    bob = AgentNode("agent-bob")
    carol = AgentNode("agent-carol")

    print("=== Phase 1: Unabhaengige Arbeit (offline, keine zentrale Koordination) ===\n")
    alice.add_task("Rechnung pruefen")
    alice.add_task("Angebot erstellen")

    bob.add_task("Angebot erstellen")  # gleiche Aufgabe wie Alice - unabhaengig!
    bob.add_task("Meeting vorbereiten")

    carol.add_task("Rechnung pruefen")
    carol.complete_task("Rechnung pruefen")  # Carol kennt Alice' Version gar nicht

    print("Lokaler Zustand vor jeder Synchronisation:")
    print_state([alice, bob, carol])

    print("\n=== Phase 2: Paarweise Synchronisation, bewusst 'unordentliche' Reihenfolge ===\n")
    bob.sync_with(carol)
    print("Nach bob <-> carol:")
    print_state([alice, bob, carol])

    alice.sync_with(bob)
    print("\nNach alice <-> bob:")
    print_state([alice, bob, carol])

    carol.sync_with(alice)
    print("\nNach carol <-> alice (Rueck-Synchronisation):")
    print_state([alice, bob, carol])

    print("\n=== Ergebnis ===\n")
    all_equal = alice.active_tasks() == bob.active_tasks() == carol.active_tasks()
    print(f"Alle drei Knoten konvergiert: {all_equal}")
    print(f"Gemeinsamer Endzustand: {sorted(alice.active_tasks())}")
    print()
    print("Bemerkenswert: 'Rechnung pruefen' ist im Endzustand PRAESENT, obwohl")
    print("Carol sie lokal als erledigt markiert hatte - weil Alice unabhaengig")
    print("eine neue, eigene Version angelegt hat, die Carol nie beobachtet hat.")
    print("Das ist Add-Wins-Semantik: keine zentrale Instanz musste entscheiden,")
    print("wer 'recht' hat - die Konvergenz ergibt sich automatisch aus der")
    print("Merge-Struktur des OR-Set.")


if __name__ == "__main__":
    main()
