"""The examples behind the submission page's dropdown.

This is the only automated protection they have. The end-to-end render test
is Docker-gated and skips without the sandbox image, so at the booth it
protects nothing; a broken example would otherwise be discovered by an
attendee who came to make art.
"""
import ast

from artwall.config import EXAMPLES, EXAMPLES_DIR


def test_every_example_resolves_to_a_file():
    for filename, _ in EXAMPLES:
        assert (EXAMPLES_DIR / filename).is_file(), filename


def test_every_example_keeps_the_draw_contract():
    """Exactly one module-level draw, taking no argument or one."""
    for filename, _ in EXAMPLES:
        module = ast.parse((EXAMPLES_DIR / filename).read_text())
        draws = [node for node in module.body
                 if isinstance(node, ast.FunctionDef) and node.name == "draw"]
        assert len(draws) == 1, filename
        args = draws[0].args
        assert len(args.args) <= 1, filename
        assert not args.posonlyargs and not args.kwonlyargs, filename


def test_no_example_is_missing_from_the_list():
    """The list drives the dropdown, so a file added without a tuple is
    invisible on the page. Nothing announces that but this test."""
    assert {p.name for p in EXAMPLES_DIR.glob("*.py")} == \
        {filename for filename, _ in EXAMPLES}


def test_labels_are_unique_and_non_empty():
    labels = [label for _, label in EXAMPLES]
    assert all(label.strip() for label in labels)
    assert len(set(labels)) == len(labels)


def test_the_scaffold_is_the_first_entry():
    """The editor opens with it, so the select has to agree on load."""
    assert EXAMPLES[0][0] == "00_scaffold.py"
