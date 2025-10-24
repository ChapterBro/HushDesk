from hushdesk.core import building_master as BM
import pytest

def test_halls_present_and_sorted():
    hs = BM.halls()
    assert set(hs) == {"Mercer","Holaday","Bridgman","Morton"}
    assert hs == sorted(hs)

def test_known_rooms_exist_by_hall():
    assert "107-2" in BM.rooms_in_hall("Mercer")
    assert "207-2" in BM.rooms_in_hall("Holaday")
    assert "307-2" in BM.rooms_in_hall("Bridgman")
    assert "418-2" in BM.rooms_in_hall("Morton")

def test_canonicalize_letter_suffix_and_lookup():
    assert BM.canonicalize_room("201B") == "201-2"
    assert BM.hall_of("201B") == "Holaday"

@pytest.mark.parametrize("bad", ["199-1","219-2","000-1","201-3","XYZ","318B9"])
def test_invalid_rooms_raise(bad):
    with pytest.raises(Exception):
        BM.canonicalize_room(bad)
