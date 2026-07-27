"""
Tests der fundamentalen CRDT-Eigenschaften des OR-Set: Kommutativitaet,
Assoziativitaet, Idempotenz. Das sind keine Implementierungsdetails,
sondern die mathematische Garantie, die CRDTs ueberhaupt nuetzlich macht
(Join-Semilattice / Strong Eventual Consistency).

Ausfuehren: pytest tests/test_or_set.py -v
"""

from crdt_ledger.or_set import ORSet


def test_add_makes_value_present():
    s = ORSet("n1")
    s.add("x")
    assert "x" in s
    assert s.values() == {"x"}


def test_remove_makes_value_absent():
    s = ORSet("n1")
    s.add("x")
    s.remove("x")
    assert "x" not in s
    assert s.values() == set()


def test_remove_without_prior_add_is_noop():
    s = ORSet("n1")
    s.remove("x")  # nichts vorhanden, das entfernt werden koennte
    assert "x" not in s


def test_merge_is_commutative():
    a = ORSet("a")
    a.add("x")
    b = ORSet("b")
    b.add("y")
    assert a.merge(b) == b.merge(a)


def test_merge_is_associative():
    a = ORSet("a")
    a.add("x")
    b = ORSet("b")
    b.add("y")
    c = ORSet("c")
    c.add("z")
    left = a.merge(b).merge(c)
    right = a.merge(b.merge(c))
    assert left == right


def test_merge_is_idempotent():
    a = ORSet("a")
    a.add("x")
    assert a.merge(a) == a


def test_concurrent_add_and_remove_add_wins():
    """
    Kernfall, den ein naives Set nicht loesen kann: Knoten A fuegt einen
    Wert hinzu, unabhaengig davon entfernt Knoten B einen Wert gleichen
    Namens (den B von frueher kennt, A aber nie gesehen hat). Nach dem
    Merge muss der Wert PRAESENT sein - Add gewinnt gegen ein Remove, das
    dieses spezifische Add nie beobachtet hat.
    """
    a = ORSet("a")
    a.add("task")  # A's eigenstaendiges Add, frischer Tag

    b = ORSet("b")
    b.add("task")  # B's eigene, fruehere Version
    b.remove("task")  # B entfernt NUR seinen eigenen Tag

    merged = a.merge(b)
    assert "task" in merged, "Add von A muss ueberleben, da B es nie beobachtet hat"


def test_same_node_add_then_remove_is_gone_after_merge():
    """Gegenprobe: entfernt derselbe Knoten seinen EIGENEN Tag, bleibt er weg."""
    a = ORSet("a")
    a.add("task")
    a.remove("task")

    b = ORSet("b")  # leerer zweiter Knoten
    merged = a.merge(b)
    assert "task" not in merged


def test_re_add_after_remove_makes_present_again():
    """Ein neues add() nach einem remove() bekommt einen neuen Tag und lebt."""
    a = ORSet("a")
    a.add("task")
    a.remove("task")
    a.add("task")  # neuer Tag, unabhaengig vom vorherigen Tag
    assert "task" in a


def test_removes_do_not_affect_unrelated_values():
    a = ORSet("a")
    a.add("keep")
    a.add("drop")
    a.remove("drop")
    assert a.values() == {"keep"}
