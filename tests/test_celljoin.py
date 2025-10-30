from hushdesk.pdf.celljoin import join_tokens


def test_join_tokens_collapses_known_pairs():
    tokens = [" ", "√", " bakk ", "H", " X"]
    assert join_tokens(tokens) == "√bakk H X"


def test_join_tokens_idempotent():
    initial = [" ", "√", " bakk ", "H", " X"]
    joined = join_tokens(initial)
    assert join_tokens(joined.split()) == joined

