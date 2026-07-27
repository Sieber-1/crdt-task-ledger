"""
Property-Test: Egal in welcher Reihenfolge oder Baum-Struktur N Replikate
gemerged werden, das Endergebnis ist immer identisch. Das ist DIE zentrale
Garantie von CRDTs (Strong Eventual Consistency) - hier nicht behauptet,
sondern ueber viele Reihenfolgen und sogar erschoepfend ueber alle
Permutationen geprueft.

Ausfuehren: pytest tests/test_convergence.py -v
"""

import itertools
import random

from crdt_ledger.or_set import ORSet


def _make_replicas() -> list[ORSet]:
    """
    Vier Replikate mit ueberlappenden, teils widerspruechlichen Operationen:
    gleiche Werte, unabhaengig voneinander hinzugefuegt oder entfernt -
    genau das Szenario, in dem Reihenfolge normalerweise Probleme machen wuerde.
    """
    r1 = ORSet("r1")
    r1.add("A")
    r1.add("B")

    r2 = ORSet("r2")
    r2.add("B")
    r2.add("C")

    r3 = ORSet("r3")
    r3.add("A")
    r3.add("C")
    r3.remove("C")  # entfernt nur r3's eigenen "C"-Tag

    r4 = ORSet("r4")
    r4.add("D")

    return [r1, r2, r3, r4]


def test_merge_order_never_changes_final_state():
    replicas = _make_replicas()

    # Referenz-Ergebnis: alle nacheinander in Ausgangsreihenfolge mergen
    reference = replicas[0]
    for r in replicas[1:]:
        reference = reference.merge(r)
    reference_values = reference.values()

    # 50 zufaellige Reihenfolgen ausprobieren - alle muessen gleich konvergieren
    random.seed(42)
    for _ in range(50):
        order = replicas[:]
        random.shuffle(order)
        result = order[0]
        for r in order[1:]:
            result = result.merge(r)
        assert result.values() == reference_values, (
            f"Reihenfolge {[x.node_id for x in order]} ergab "
            f"{result.values()}, erwartet {reference_values}"
        )


def test_pairwise_merge_tree_matches_linear_merge():
    """
    Merged nicht nur linear, sondern in unterschiedlichen Baum-Strukturen
    (z.B. (r1+r2)+(r3+r4) vs r1+(r2+(r3+r4))) - muss trotzdem gleich sein.
    """
    r1, r2, r3, r4 = _make_replicas()

    linear = r1.merge(r2).merge(r3).merge(r4)
    tree = (r1.merge(r2)).merge(r3.merge(r4))
    balanced = r1.merge(r2.merge(r3.merge(r4)))

    assert linear.values() == tree.values() == balanced.values()


def test_all_permutations_of_three_nodes_converge():
    """Erschoepfende Pruefung: ALLE 6 moeglichen Reihenfolgen von 3 Knoten."""
    a = ORSet("a")
    a.add("x")
    a.add("y")

    b = ORSet("b")
    b.add("y")
    b.remove("y")

    c = ORSet("c")
    c.add("z")

    results = []
    for perm in itertools.permutations([a, b, c]):
        merged = perm[0]
        for node in perm[1:]:
            merged = merged.merge(node)
        results.append(merged.values())

    assert all(r == results[0] for r in results), (
        f"Nicht alle Permutationen konvergieren: {results}"
    )


def test_repeated_merge_of_same_pair_is_stable():
    """Mehrfaches Mergen desselben Paars darf den Zustand nicht veraendern
    (Idempotenz auf Anwendungsebene, nicht nur fuer identische Objekte)."""
    a = ORSet("a")
    a.add("x")
    b = ORSet("b")
    b.add("y")

    once = a.merge(b)
    twice = once.merge(b).merge(a).merge(b)

    assert once.values() == twice.values()
