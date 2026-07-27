"""
Demo: Operation-based OR-Set - zeigt den Fall, der state-based CRDTs nie
begegnet: eine Remove-Operation trifft VOR ihrer zugehoerigen Add-Operation
ein (unterschiedliche Netzwerkpfade, unterschiedliche Latenz).

Ausfuehren: python op_based_demo.py
"""

from crdt_ledger.op_based import OpBasedORSet


def main() -> None:
    print("=== Operation-based OR-Set: verspaetete Kausalitaet ===\n")

    origin = OpBasedORSet("origin")
    add_op = origin.add("Rechnung pruefen")
    print(f"origin legt an: {origin.values()}")

    remove_ops = origin.remove("Rechnung pruefen")
    print(f"origin entfernt wieder: {origin.values()}")

    print("\n--- Simuliere Netzwerk, das Remove VOR dem Add zustellt ---\n")
    replica = OpBasedORSet("replica")

    print("1. Remove-Operation kommt zuerst an (Netzwerk-Eigenart)...")
    for op in remove_ops:
        replica.apply_remote(op)
    print(f"   replica-Zustand: {replica.values()}")
    print(f"   zurueckgestellt (pending): {len(replica._pending_removes)} Operation(en)")
    print("   -> 'Rechnung pruefen' erscheint (noch) NICHT als entfernt, weil")
    print("      replica den Wert ueberhaupt noch nicht kennt.\n")

    print("2. Jetzt trifft die (verspaetete) Add-Operation ein...")
    replica.apply_remote(add_op)
    print(f"   replica-Zustand: {replica.values()}")
    print(f"   zurueckgestellt (pending): {len(replica._pending_removes)} Operation(en)")
    print("   -> Das aufgeschobene Remove wird jetzt nachgeholt.\n")

    print(f"Endzustand identisch zu origin: {replica.values() == origin.values()}")
    print("\nGenau das ist der Unterschied zu state-based CRDTs (or_set.py):")
    print("dort kaeme immer der GESAMTE Zustand an - hier muss die kausale")
    print("Abhaengigkeit zwischen einzelnen Operationen explizit gehandhabt werden.")


if __name__ == "__main__":
    main()
