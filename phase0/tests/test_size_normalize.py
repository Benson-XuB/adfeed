"""Letter sizes must stay unique — never fold XXXL into L or 4XL into 5XL."""
from adfeed.attribute_normalizer import normalize_size
from adfeed.variant_attributes import _clean_size


def test_xxxl_is_not_l():
    assert normalize_size("XXXL") == "XXXL"
    assert normalize_size("xxxl") == "XXXL"
    assert _clean_size("XXXL") == "XXXL"


def test_xl_is_not_l():
    assert normalize_size("XL") == "XL"
    assert _clean_size("XL") == "XL"


def test_xxl_is_not_l():
    assert normalize_size("XXL") == "XXL"
    assert _clean_size("XXL") == "XXL"


def test_4xl_and_5xl_stay_distinct():
    assert normalize_size("4XL") == "4XL"
    assert normalize_size("5XL") == "5XL"
    assert _clean_size("4XL") != _clean_size("5XL")
    assert _clean_size("5XL") == "5XL"


def test_2xl_not_collapsed_with_xxl_token():
    """Keep 2XL as 2XL so a catalog that uses both 2XL and XXL does not collide."""
    assert normalize_size("2XL") == "2XL"
    assert normalize_size("XXL") == "XXL"


def test_chinese_one_size_and_letter_with_suffix():
    assert normalize_size("均码") == "One Size"
    assert normalize_size("XL码") == "XL"
    assert normalize_size("L码") == "L"


def test_jeans_size_set_unique():
    sizes = ["S", "M", "L", "XL", "XXL", "XXXL"]
    out = [_clean_size(s) for s in sizes]
    assert len(out) == len(set(out))
    assert out == ["S", "M", "L", "XL", "XXL", "XXXL"]
