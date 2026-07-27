# CRDT Task Ledger

**Verteilte Aufgabenkoordination ohne zentrale Kontrollinstanz** — ein OR-Set
(Conflict-free Replicated Data Type) von Grund auf selbst implementiert,
angewendet auf ein Multi-Agent-Szenario: mehrere unabhängige Agent-Knoten
teilen sich eine Aufgabenliste, können "offline" arbeiten, und konvergieren
nach dem Zusammenführen garantiert zum selben Zustand — unabhängig von
Reihenfolge, Timing oder ob eine zentrale Instanz je involviert war.

## Schnellstart (Kern-Funktionalität, keine externen Abhängigkeiten außer pytest)

```bash
git clone https://github.com/Sieber-1/crdt-task-ledger.git
cd crdt-task-ledger
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

PYTHONPATH=. pytest tests/ -v          # 20 Tests (2 NATS-Tests werden ohne Server uebersprungen)
PYTHONPATH=. python demo.py            # 3 Knoten, In-Prozess-Synchronisation
```

## Mit echtem Message-Broker (NATS)

```bash
# NATS-Server separat starten (https://nats.io)
nats-server -p 4222 &

PYTHONPATH=. pytest tests/test_broker_integration.py -v   # jetzt: 2/2 statt skipped
PYTHONPATH=. python broker_demo.py                          # echte Netzwerk-Propagation
```

## Das Problem, das CRDTs lösen

Zwei Agenten arbeiten unabhängig, ohne zentrale Koordination. Agent A legt
eine Aufgabe an. Unabhängig davon markiert Agent B dieselbe Aufgabe als
erledigt (von einer älteren, eigenen Version, die A nie gesehen hat). Wer
"gewinnt", wenn sich beide synchronisieren? Ohne zentrale Instanz, die
entscheidet, kann ein naives Set das nicht widerspruchsfrei lösen.

**Die OR-Set-Lösung:** Jede `add()`-Operation bekommt eine eindeutige Marke
(Tag). `remove()` entfernt nur die Tags, die zu diesem Zeitpunkt lokal
*beobachtet* wurden. Ein unabhängiges `add()` mit neuem Tag überlebt ein
älteres `remove()` automatisch — "Add-Wins"-Semantik.

Die `merge()`-Operation ist reine Mengenvereinigung — dadurch beweisbar
kommutativ, assoziativ und idempotent (Join-Semilattice). Das ist die
zentrale Garantie: egal in welcher Reihenfolge oder wie oft Replikate
zusammengeführt werden, alle konvergieren zum selben Endzustand (**Strong
Eventual Consistency**) — ganz ohne zentrale Kontrollinstanz.

## Architektur

```
crdt_ledger/
├── or_set.py     # Die CRDT selbst: add(), remove(), merge() - reines Python, 0 Dependencies
├── node.py       # AgentNode: OR-Set + sync_with() fuer direkte In-Prozess-Synchronisation
└── broker.py     # NetworkedAgentNode: dieselbe Logik, aber ueber echten NATS-Broker

tests/
├── test_or_set.py             # CRDT-Gesetze: Kommutativitaet, Assoziativitaet, Idempotenz
├── test_convergence.py        # Konvergenz ueber 50 zufaellige + alle 6 Permutationen von Reihenfolgen
├── test_node.py               # Multi-Agent-Szenario inkl. des entscheidenden Concurrent-Falls
└── test_broker_integration.py # Dieselbe Konvergenz, aber ueber echte NATS-Nachrichten

demo.py            # 3 Knoten, In-Prozess-Synchronisation via sync_with()
broker_demo.py      # 3 Knoten, echte Netzwerk-Propagation via NATS
```

## Was die Tests tatsächlich beweisen

Nicht nur "es funktioniert im Demo-Lauf", sondern:

- **Kommutativität, Assoziativität, Idempotenz** einzeln bewiesen (`test_or_set.py`)
- **50 zufällige Merge-Reihenfolgen** von 4 Replikaten konvergieren identisch (`test_convergence.py`)
- **Alle 6 Permutationen** von 3 Knoten erschöpfend geprüft, nicht nur stichprobenartig
- **Der entscheidende Concurrent-Fall** (unabhängiges Add überlebt fremdes Remove) — sowohl
  in-Prozess (`test_node.py`) als auch über echte NATS-Nachrichten (`test_broker_integration.py`)

## Ein echter Bug, den das Testen gefunden hat

Beim ersten Versuch der NATS-Integration konvergierten die Knoten **nicht** —
jeder sah nur seine eigene Aufgabe. Ursache: `_deserialize()` setzte die
`node_id` des empfangenen Zustands versehentlich auf die des *empfangenden*
statt des *sendenden* Knotens, wodurch der Echo-Filter jede fremde Nachricht
fälschlich verwarf. Behoben durch korrektes Auslesen der Absender-ID aus der
Nachricht selbst. Genau der Grund, warum "sollte funktionieren" durch "läuft
nachweislich" ersetzt werden muss.

## Grenzen 

- **Speicherwachstum:** Tombstones (`_removes`) werden nie aufgeräumt. Für
  eine Demo unerheblich, in Produktion bräuchte man Garbage Collection
  (z.B. via Versionsvektoren), um alte Tags irgendwann sicher zu entfernen.
- **Kein Netzwerk-Partitions-Handling über die CRDT-Garantie hinaus:**
  Konvergenz ist garantiert, *sobald* alle Nachrichten angekommen sind. Wie
  lange das dauert (Verzögerung, dauerhafte Partition) ist Sache des
  Transports (NATS), nicht der CRDT selbst.
- **broker.py überträgt den vollständigen Zustand** bei jeder Änderung, nicht
  nur das Delta — korrekt (wegen Idempotenz), aber nicht bandbreitenoptimal.
  Eine Produktivversion würde nur Deltas übertragen.
- **Kein Byzantine-Fault-Tolerance:** Ein böswilliger oder fehlerhafter
  Knoten könnte beliebige Tags fälschen. CRDTs lösen Nebenläufigkeit, nicht
  Vertrauen.

## Was dieses Projekt zeigt

- CRDT-Algorithmus **selbst implementiert**, nicht aus einer Library
  importiert — der Punkt ist, die Merge-Semantik wirklich verstanden zu
  haben, nicht sie zu benutzen.
- Mathematische Garantien (Kommutativität etc.) nicht nur behauptet, sondern
  über Zufallsstichproben und erschöpfende Permutationen tatsächlich geprüft.
- Echte Message-Broker-Integration (NATS) statt Simulation — inklusive eines
  echten Bugs, der nur durch tatsächliches Testen auffiel.
- Sauber getrennte Kern-Logik (0 Dependencies) von optionaler
  Infrastruktur-Anbindung (NATS) — die Kern-Tests laufen überall, ohne
  Server-Setup vorauszusetzen.

## Lizenz

MIT — siehe [LICENSE](LICENSE)

---

**Autor:** Sieber Mirani
