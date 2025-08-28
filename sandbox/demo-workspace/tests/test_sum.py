import sys
sys.path.append("/workspace/student")  # import student code

from student import add

def test_add_small():
    assert add(1, 2) == 3

def test_add_large():
    assert add(10_000, 1) == 10_001
