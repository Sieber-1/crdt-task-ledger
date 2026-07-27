"""
Demo: 3 Agent-Knoten kommunizieren ueber einen ECHTEN NATS-Message-Broker
(nicht simuliert innerhalb eines Prozesses) und konvergieren garantiert
zum selben Zustand.

Voraussetzung: ein laufender NATS-Server.
    nats-server -p 4222

Ausfuehren: python broker_demo.py
"""

import asyncio

from crdt_ledger.broker import NetworkedAgentNode


async def main() -> None:
    print("Verbinde 3 Knoten mit NATS-Broker (nats://localhost:4222)...")
    alice = NetworkedAgentNode("agent-alice")
    bob = NetworkedAgentNode("agent-bob")
    carol = NetworkedAgentNode("agent-carol")

    try:
        await alice.connect()
        await bob.connect()
        await carol.connect()
        await asyncio.sleep(0.3)
        print("Verbunden.\n")

        print("=== Jeder Knoten legt unabhaengig eine Aufgabe an ===")
        await alice.add_task("Rechnung pruefen")
        await bob.add_task("Angebot erstellen")
        await carol.add_task("Meeting vorbereiten")

        print("Warte auf Propagation ueber den Broker...")
        await asyncio.sleep(0.5)

        print("\n=== Zustand nach echter Netzwerk-Synchronisation ===")
        print(f"  agent-alice: {sorted(alice.active_tasks())}")
        print(f"  agent-bob:   {sorted(bob.active_tasks())}")
        print(f"  agent-carol: {sorted(carol.active_tasks())}")

        converged = alice.active_tasks() == bob.active_tasks() == carol.active_tasks()
        print(f"\nKonvergiert (echte Netzwerkuebertragung): {converged}")

    except Exception as e:
        print(f"\nFehler: {e}")
        print("Laeuft ein NATS-Server auf localhost:4222? Starten mit:")
        print("  nats-server -p 4222")
    finally:
        await alice.close()
        await bob.close()
        await carol.close()


if __name__ == "__main__":
    asyncio.run(main())
