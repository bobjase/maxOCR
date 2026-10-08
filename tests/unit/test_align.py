from maxocr.align import align


def test_positional_when_lengths_match():
    assert align("0O8", "OO8") == ("positional", [0, 1, 2], 0)


def test_collapsed_double_is_one_deletion():
    method, mapping, ins = align("A00B", "A0B")
    assert method == "edit" and ins == 0
    assert mapping.count(None) == 1 and mapping[0] == 0 and mapping[3] == 2


def test_insertion_counted():
    method, mapping, ins = align("AB", "A1B")
    assert (mapping, ins) == ([0, 2], 1)


def test_empty_output():
    assert align("AB", "") == ("edit", [None, None], 0)
