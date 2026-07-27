#!/bin/bash
# ============================================================
# GitHub Setup: CRDT Task Ledger
# ============================================================
# 1. Auf GitHub ein NEUES, LEERES Repository anlegen: crdt-task-ledger
#    Public, OHNE README/LICENSE/.gitignore
# 2. Dieses Skript im Projektordner ausfuehren: bash github_setup.sh
# ============================================================

set -e

echo "=== CRDT Task Ledger: Git-Repository wird vorbereitet ==="

if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null
rm -f .env

echo ""
echo "--- Commit 1/4: Projekt-Grundgerüst ---"
git add .gitignore LICENSE requirements.txt pytest.ini
git commit -m "Initial project setup: dependencies, config, license"

echo "--- Commit 2/4: OR-Set CRDT Kernimplementierung ---"
git add crdt_ledger/or_set.py crdt_ledger/__init__.py
git commit -m "Implement OR-Set CRDT from scratch

Observed-Remove Set mit add(), remove(), merge(). Reines Python, keine
externen Abhaengigkeiten. Merge ist reine Mengenvereinigung - dadurch
beweisbar kommutativ, assoziativ und idempotent (Join-Semilattice)."

echo "--- Commit 3/6: Multi-Agent-Schicht und echte Broker-Integration ---"
git add crdt_ledger/node.py crdt_ledger/broker.py demo.py broker_demo.py
git commit -m "Add AgentNode abstraction and real NATS broker integration

AgentNode kapselt das OR-Set fuer ein Multi-Agent-Task-Ledger-Szenario mit
direkter sync_with()-Synchronisation. NetworkedAgentNode nutzt denselben
Algorithmus ueber einen echten NATS-Message-Broker fuer Netzwerk-Propagation."

echo "--- Commit 4/6: Netzwerk-Partitions-Simulation ---"
git add crdt_ledger/partition.py tests/test_partition.py partition_demo.py
git commit -m "Add network partition simulation

PartitionedNetwork simuliert Gruppen von Knoten, die sich zeitweise nicht
erreichen koennen, aber unabhaengig weiterarbeiten. Nach heal() konvergiert
das gesamte Netzwerk garantiert - auch bei widersprechenden, nebenlaeufigen
Operationen waehrend der Trennung."

echo "--- Commit 5/6: Operation-based (Delta) CRDT Variante ---"
git add crdt_ledger/op_based.py tests/test_op_based.py op_based_demo.py
git commit -m "Add operation-based OR-Set (CmRDT) variant

Ergaenzt die state-based Variante (or_set.py) um eine operation-based
Implementierung: Replikate tauschen einzelne Add/Remove-Operationen statt
vollstaendiger Zustaende aus. Loest kausale Abhaengigkeiten (Remove nach
seinem Add) explizit ueber eine Pending-Queue statt sie zu ignorieren."

echo "--- Commit 6/6: Tests und Dokumentation ---"
git add tests/test_or_set.py tests/test_convergence.py tests/test_node.py tests/test_broker_integration.py README.md
git commit -m "Add core test suite and documentation

CRDT-Gesetze (Kommutativitaet, Assoziativitaet, Idempotenz), Konvergenz
ueber randomisierte und erschoepfende Permutationen, Multi-Agent-Szenarien
sowie echte NATS-Integrationstests (mit Skip-Mechanismus ohne Server)."

echo ""
echo "=== Alle Commits erstellt. Aktuelle Historie: ==="
git log --oneline

echo ""
read -p "GitHub-Repo-URL eingeben: " REPO_URL
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git push -u origin main

echo ""
echo "=== Fertig! Repository ist live. ==="
