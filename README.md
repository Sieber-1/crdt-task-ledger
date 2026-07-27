# CRDT Task Ledger

**Verteilte Aufgabenkoordination ohne zentrale Kontrollinstanz** — CRDTs
(Conflict-free Replicated Data Types) von Grund auf selbst implementiert,
in zwei Varianten (state-based und operation-based), inklusive echter
Netzwerk-Partitions-Simulation und echter Message-Broker-Integration (NATS).

Kernszenario: mehrere unabhängige Agent-Knoten teilen sich eine
Aufgabenliste, arbeiten "offline" oder durch Netzwerk-Partitionen getrennt
weiter, und konvergieren nach dem Zusammenführen garantiert zum selben
Zustand — unabhängig von Reihenfolge, Timing, Partitionierung, oder ob
je eine zentrale Instanz involviert war.

## Schnellstart (Kern-Funktionalität, keine externen Abhängigkeiten außer pytest)

```bash
git clone https://github.com/Sieber-1/crdt-task-ledger.git
cd crdt-task-ledger
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

PYTHONPATH=. pytest tests/ -v          # 36 Tests (2 NATS-Tests werden ohne Server uebersprungen)
PYTHONPATH=. python demo.py            # Basis: 3 Knoten, In-Prozess-Synchronisation
PYTHONPATH=. python partition_demo.py  # Netzwerk-Partition: 5 Knoten, zwei getrennte Gruppen
PYTHONPATH=. python op_based_demo.py   # Operation-based Variante: kausale Reihenfolge
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
├── or_set.py     # State-based CRDT (CvRDT): add(), remove(), merge() - 0 Dependencies
├── op_based.py   # Operation-based CRDT (CmRDT): einzelne Operationen statt Zustands-Merge
├── node.py       # AgentNode: OR-Set + sync_with() fuer In-Prozess-Synchronisation
├── partition.py  # PartitionedNetwork: simuliert Netzwerk-Partitionen zwischen Knotengruppen
└── broker.py     # NetworkedAgentNode: dieselbe Logik ueber echten NATS-Broker

tests/
├── test_or_set.py              # CRDT-Gesetze: Kommutativitaet, Assoziativitaet, Idempotenz
├── test_convergence.py         # Konvergenz ueber 50 zufaellige + alle 6 Permutationen
├── test_node.py                # Multi-Agent-Szenario inkl. des entscheidenden Concurrent-Falls
├── test_partition.py           # Partitionierung, unabhaengiges Arbeiten, Heilung, Wiederholung
├── test_op_based.py            # Kausale Reihenfolge, Duplikat-Sicherheit, Nebenlaeufigkeit
└── test_broker_integration.py  # Dieselbe Konvergenz ueber echte NATS-Nachrichten

demo.py              # 3 Knoten, In-Prozess-Synchronisation via sync_with()
partition_demo.py    # 5 Knoten, zwei Netzwerk-Partitionen, Heilung
op_based_demo.py     # Operation-based Variante: verspaetet eintreffendes Remove
broker_demo.py       # 3 Knoten, echte Netzwerk-Propagation via NATS
```

## State-based vs. operation-based - der Unterschied, den viele Tutorials überspringen

**or_set.py (state-based / CvRDT):** Replikate tauschen ihren vollständigen
Zustand aus. `merge()` muss kommutativ, assoziativ, idempotent sein.
Zustellung darf beliebig oft wiederholt werden und in beliebiger Reihenfolge
ankommen — einfach zu beweisen, aber mehr Bandbreite bei häufigen kleinen
Änderungen.

**op_based.py (operation-based / CmRDT):** Replikate tauschen nur einzelne
Operationen aus (Add/Remove) — deutlich weniger Bandbreite. Dafür brauchen
*kausal abhängige* Operationen eine garantierte Reihenfolge: ein
`Remove(tag)` darf erst wirken, nachdem das zugehörige `Add(value, tag)`
angewendet wurde. `op_based.py` löst das mit einer expliziten
Pending-Queue statt das Problem zu ignorieren oder wegzudefinieren.

**Eine Feinheit, die beim genauen Durchdenken auffällt** (siehe Docstring in
`op_based.py`): Lehrbuch-CmRDTs fordern oft "exactly-once"-Zustellung, weil
viele Operationstypen (z.B. Counter-Increment) bei doppelter Anwendung
falsche Werte ergäben. Für OR-Set gilt das nicht zwingend — jede Operation
trägt einen global eindeutigen Tag, wodurch Add/Remove auf Mengen-Ebene von
Natur aus idempotent sind. Die Deduplizierung ist hier eher Demonstration
der allgemeinen CmRDT-Praxis als eine Notwendigkeit für Korrektheit bei
genau dieser Datenstruktur.

## Netzwerk-Partitionen (partition.py)

Trifft direkt den häufigsten Praxisfall verteilter Systeme: kein Fehler,
sondern Normalzustand. `PartitionedNetwork` teilt eine Menge von Knoten in
isolierte Gruppen; `try_sync()` verweigert Synchronisation über
Partitionsgrenzen hinweg (wie ein echter Netzwerkausfall), erlaubt sie aber
innerhalb einer Gruppe uneingeschränkt. Nach `heal()` konvergiert das
gesamte Netzwerk garantiert — auch wenn beide Seiten währenddessen
widersprüchliche, nebenläufige Operationen auf denselben Werten
durchgeführt haben (siehe `test_concurrent_conflicting_operations_across_partition_resolve_correctly`).

## Was die Tests tatsächlich beweisen

Nicht nur "es funktioniert im Demo-Lauf", sondern (36 Tests gesamt):

- **Kommutativität, Assoziativität, Idempotenz** einzeln bewiesen (`test_or_set.py`)
- **50 zufällige Merge-Reihenfolgen** von 4 Replikaten konvergieren identisch (`test_convergence.py`)
- **Alle 6 Permutationen** von 3 Knoten erschöpfend geprüft, nicht nur stichprobenartig
- **Der entscheidende Concurrent-Fall** (unabhängiges Add überlebt fremdes Remove) — in-Prozess,
  über Partitionsgrenzen hinweg, per Operation und über echte NATS-Nachrichten (vier verschiedene Tests,
  eine Eigenschaft)
- **Kausale Reihenfolge** bei verspätet eintreffenden Operationen (`test_op_based.py`) — inklusive
  Pending-Queue-Mechanismus für Remove-vor-Add
- **Partitionierung und Heilung**, auch über mehrere aufeinanderfolgende Zyklen (`test_partition.py`)

## Ein echter Bug, den das Testen gefunden hat

Beim ersten Versuch der NATS-Integration konvergierten die Knoten **nicht** —
jeder sah nur seine eigene Aufgabe. Ursache: `_deserialize()` setzte die
`node_id` des empfangenen Zustands versehentlich auf die des *empfangenden*
statt des *sendenden* Knotens, wodurch der Echo-Filter jede fremde Nachricht
fälschlich verwarf. Behoben durch korrektes Auslesen der Absender-ID aus der
Nachricht selbst. Genau der Grund, warum "sollte funktionieren" durch "läuft
nachweislich" ersetzt werden muss.

## Grenzen — ehrlich benannt

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
