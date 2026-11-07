from calculator import add

def test_addition():
    assert add(2,3)==5

def test_negative_control():
    assert add(2,3)==6
