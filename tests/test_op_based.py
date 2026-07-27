"""
Tests fuer die operation-based OR-Set-Variante (CmRDT).

Im Fokus: die Eigenschaften, die state-based CRDTs NICHT brauchen, aber
operation-based CRDTs zwingend erfuellen muessen - vor allem kausale
Reihenfolge fuer abhaengige Operationen (Remove nach seinem Add).

Ausfuehren: pytest tests/test_op_based.py -v
"""

from crdt_ledger.op_based import AddOp, OpBasedORSet, RemoveOp


def test_local_add_and_remove():
    s = OpBasedORSet("n1")
    s.add("task")
    assert "task" in s
    s.remove("task")
    assert "task" not in s


def test_operations_returned_for_broadcasting():
    s = OpBasedORSet("n1")
    add_op = s.add("task")
    assert isinstance(add_op, AddOp)
    assert add_op.value == "task"

    remove_ops = s.remove("task")
    assert len(remove_ops) == 1
    assert isinstance(remove_ops[0], RemoveOp)
    assert remove_ops[0].tag == add_op.tag


def test_remote_add_then_remove_in_correct_order():
    """Normalfall: Operationen kommen in kausal korrekter Reihenfolge an."""
    a = OpBasedORSet("a")
    add_op = a.add("task")

    b = OpBasedORSet("b")
    b.apply_remote(add_op)
    assert "task" in b

    remove_ops = a.remove("task")
    for op in remove_ops:
        b.apply_remote(op)
    assert "task" not in b


def test_remove_arriving_before_its_add_is_buffered_then_resolved():
    """
    Der entscheidende Fall fuer operation-based CRDTs: das Netzwerk liefert
    Remove(tag) VOR dem zugehoerigen Add(value, tag) aus (z.B. weil beide
    Nachrichten unterschiedliche Wege durchs Netz nehmen). Ein state-based
    CRDT haette dieses Problem nie, weil dort immer der GANZE Zustand
    ankommt. Hier muss das Replikat das verfrueht ankommende Remove
    zurueckhalten, bis das Add angewendet wurde - und darf es NICHT
    verwerfen oder faelschlich ignorieren.
    """
    a = OpBasedORSet("a")
    add_op = a.add("task")
    remove_ops = a.remove("task")
    assert len(remove_ops) == 1
    remove_op = remove_ops[0]

    b = OpBasedORSet("b")

    # Bewusst falsche Reihenfolge: Remove kommt VOR dem Add an
    b.apply_remote(remove_op)
    # Ohne das zugehoerige Add darf "task" noch nicht als entfernt gelten -
    # b weiss ja noch gar nicht, dass "task" ueberhaupt existiert
    assert "task" not in b
    assert remove_op.tag in b._pending_removes, (
        "Verfruehtes Remove muss zurueckgestellt werden, nicht verworfen"
    )

    # Jetzt kommt das Add nach - das zurueckgestellte Remove muss greifen
    b.apply_remote(add_op)
    assert "task" not in b, "Nach Nachlieferung des Add muss das aufgeschobene Remove wirken"
    assert remove_op.tag not in b._pending_removes


def test_duplicate_remote_delivery_is_safe():
    """Dieselbe Operation zweimal remote anzuwenden darf den Zustand nicht veraendern
    (Netzwerk-Retries duerfen keine doppelte Wirkung haben)."""
    a = OpBasedORSet("a")
    add_op = a.add("task")

    b = OpBasedORSet("b")
    b.apply_remote(add_op)
    b.apply_remote(add_op)  # Duplikat, z.B. durch Netzwerk-Retry
    b.apply_remote(add_op)  # noch ein Duplikat

    assert b.values() == {"task"}


def test_concurrent_add_survives_independent_remove_op_based():
    """
    Dieselbe Kerneigenschaft wie beim state-based OR-Set (test_or_set.py),
    hier aber ueber einzelne Operationen statt Zustands-Merge geprueft:
    ein unabhaengiges Add ueberlebt ein Remove, das es nie beobachtet hat.
    """
    a = OpBasedORSet("a")
    a_add = a.add("Rechnung pruefen")  # A's unabhaengiges Add

    b = OpBasedORSet("b")
    b_add = b.add("Rechnung pruefen")  # B's eigene, fruehere Version
    b_removes = b.remove("Rechnung pruefen")  # B entfernt NUR seinen eigenen Tag

    # Beide Replikate erhalten am Ende alle Operationen des jeweils anderen
    a.apply_remote(b_add)
    for op in b_removes:
        a.apply_remote(op)

    b.apply_remote(a_add)

    assert "Rechnung pruefen" in a, "A's eigenes Add darf durch B's fremdes Remove nicht verloren gehen"
    assert "Rechnung pruefen" in b


def test_operations_converge_regardless_of_application_order():
    """
    Property-Test: nebenlaeufige (kausal unabhaengige) Operationen duerfen
    in beliebiger Reihenfolge angewendet werden - das Ergebnis muss trotzdem
    identisch konvergieren. (Kausal ABHAENGIGE Operationen - Remove nach
    seinem eigenen Add - werden hier bewusst in korrekter Reihenfolge
    gehalten; genau DAS zu unterscheiden ist ja der Punkt dieses Moduls.)
    """
    origin = OpBasedORSet("origin")
    add_x = origin.add("x")
    add_y = origin.add("y")
    remove_x = origin.remove("x")[0]  # kausal abhaengig von add_x

    # Zwei nebenlaeufige, unabhaengige Ereignisse woanders:
    other = OpBasedORSet("other")
    add_z = other.add("z")

    # Alle Operationen in EINER moeglichen Reihenfolge sammeln, wobei
    # remove_x IMMER nach add_x steht (kausale Abhaengigkeit gewahrt),
    # add_y und add_z aber beliebig dazwischen einsortiert werden koennen.
    import itertools

    fixed_pairs = [add_x, remove_x]  # muss diese relative Reihenfolge behalten
    free_ops = [add_y, add_z]

    results = []
    for perm in itertools.permutations(free_ops):
        # add_x, remove_x IMMER in dieser Reihenfolge, frei permutierte
        # Operationen an beliebigen (aber gueltigen) Stellen eingefuegt
        sequence = [add_x, perm[0], perm[1], remove_x]
        replica = OpBasedORSet("replica")
        for op in sequence:
            replica.apply_remote(op)
        results.append(replica.values())

    assert all(r == results[0] for r in results), f"Nicht alle Reihenfolgen konvergieren: {results}"
    assert results[0] == {"y", "z"}  # x wurde entfernt, y und z bleiben
