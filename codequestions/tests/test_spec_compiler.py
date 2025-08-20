# codequestions/tests/test_spec_compiler.py
import pytest
from codequestions.spec_compiler import compile_yaml_to_spec, SpecError

def test_standard_io_example():
    yaml_text = """\
type: standardIo
description: |
  Add two numbers
tests:
  - name: case1
    stdin: |
      2
      3
    stdout: "5"
"""
    compiled = compile_yaml_to_spec(yaml_text)
    assert compiled["type"] == "standardIo"
    assert compiled["tests"][0]["stdout"].endswith("\n")  # newline normalized

def test_function_example():
    yaml_text = """\
type: function
description: factorial
function:
  name: factorial
  arguments:
    - name: n
      type: integer
tests:
  - name: base
    args: {n: 0}
    expected: 1
"""
    compiled = compile_yaml_to_spec(yaml_text)
    assert compiled["function"]["name"] == "factorial"
    assert compiled["tests"][0]["args"] == [0]

def test_oop_example():
    yaml_text = """\
type: oop
description: ShoppingCart
class:
  name: ShoppingCart
  methods:
    - name: init
    - name: total
tests:
  - name: emptyCart
    setup:
      - action: create
        class: ShoppingCart
        var: cart
    actions:
      - action: call
        var: cart
        method: total
        expected: 0.0
"""
    compiled = compile_yaml_to_spec(yaml_text)
    assert compiled["class"]["methods"][0]["name"] == "__init__"
    assert compiled["tests"][0]["steps"][0]["expected"] == 0.0

def test_bad_yaml_raises():
    with pytest.raises(SpecError):
        compile_yaml_to_spec("not: [valid")
