"""
Demo: Ein Netzwerk aus 5 Agent-Knoten wird in zwei Gruppen partitioniert
(kein Netzwerkpfad zwischen den Gruppen). Beide Seiten arbeiten unabhaengig
weiter. Nach dem Heilen der Partition konvergieren alle Knoten garantiert -
selbst bei widerspruechlichen, nebenlaeufigen Operationen auf beiden Seiten.

Ausfuehren: python partition_demo.py
"""

from crdt_ledger.node import AgentNode
from crdt_ledger.partition import PartitionedNetwork


def show(net: PartitionedNetwork, label: str) -> None:
    print(f"\n{label}")
    for node_id, node in net.nodes.items():
        print(f"  {node_id}: {sorted(node.active_tasks())}")
    print(f"  Konvergiert: {net.all_converged()}")


def main() -> None:
    nodes = [AgentNode(n) for n in ["alice", "bob", "carol", "dave", "erin"]]
    net = PartitionedNetwork(nodes)
    alice, bob, carol, dave, erin = nodes

    print("=== Netzwerk wird partitioniert: [alice, bob] | [carol, dave, erin] ===")
    net.partition(["alice", "bob"], ["carol", "dave", "erin"])
    print("Kein Netzwerkpfad zwischen den beiden Gruppen.\n")

    print("--- Beide Seiten arbeiten unabhaengig weiter ---")
    alice.add_task("Angebot pruefen")
    bob.add_task("Vertrag unterschreiben")

    carol.add_task("Rechnung pruefen")
    carol.complete_task("Rechnung pruefen")  # Carol-Seite: aus ihrer Sicht erledigt
    dave.add_task("Rechnung pruefen")  # Dave (gleiche Gruppe wie Carol), unabhaengig neu angelegt

    net.sync_all_reachable()
    show(net, "Zustand WAEHREND der Partition (nur innerhalb der Gruppen synchronisiert):")

    print("\n=== Partition heilt - Netzwerkpfad wiederhergestellt ===")
    net.heal()
    net.sync_all_reachable()
    show(net, "Zustand NACH dem Heilen:")

    print("\nBemerkenswert: 'Rechnung pruefen' ist praesent, obwohl Carol sie auf")
    print("ihrer Seite lokal als erledigt markiert hatte - weil Dave (in derselben")
    print("Partitionsgruppe, aber ohne von Carols Historie zu wissen) unabhaengig")
    print("eine neue Version anlegte. Genau dieselbe Add-Wins-Garantie wie ohne")
    print("Partition - eine Netzwerktrennung aendert an der Konvergenz-Garantie nichts.")


if __name__ == "__main__":
    main()
