"""The expected state of a step, from what its action changed (#469)."""

import re
from datetime import UTC, datetime

import pytest

from app.contracts_gen.common_schema import Action, ExpectedState, Target
from app.ports.models import ObservedState
from app.verifier import RuleVerifier
from app.verifier.change import observed_change

TODO_EMPTY = '- main:\n  - heading "todos" [level=1]\n  - textbox "What needs to be done?"'
TODO_TYPED = TODO_EMPTY + ": Buy milk"
TODO_ADDED = (
    TODO_EMPTY
    + """
  - list:
    - listitem:
      - checkbox "Toggle Todo"
      - text: Buy milk
      - button "Delete"
  - status: 1 item left"""
)
TODO_DONE = TODO_ADDED.replace('checkbox "Toggle Todo"', 'checkbox "Toggle Todo" [checked]')


def state(url: str, aria: str, query: str | None = None) -> ObservedState:
    return ObservedState(url=url, query=query, title="t", aria_excerpt=aria, captured_at=datetime.now(UTC))


def test_typing_records_the_field_value() -> None:
    target = Target(role="textbox", name="What needs to be done?")

    change = observed_change(
        state("/todomvc/", TODO_EMPTY),
        state("/todomvc/", TODO_TYPED),
        Action(type="fill", value="Buy milk"),
        target,
    )

    assert change is not None
    assert change.model_dump(exclude_none=True) == {
        "field_values": [{"role": "textbox", "name": "What needs to be done?", "value": "Buy milk"}]
    }


def test_pressing_enter_records_what_appeared() -> None:
    # The spike's TodoMVC run: the plan guessed a list item named "Buy milk" and an input that goes away.
    change = observed_change(
        state("/todomvc/", TODO_TYPED),
        state("/todomvc/", TODO_ADDED),
        Action(type="press", value="Enter"),
        Target(role="textbox", name="What needs to be done?"),
    )

    assert change is not None
    assert change.visible is not None
    assert [(v.role, v.name) for v in change.visible] == [
        ("status", "1 item left"),
        ("button", "Delete"),
        ("checkbox", "Toggle Todo"),
    ]
    assert change.url_matches is None and change.absent is None


def test_ticking_a_checkbox_records_it_checked() -> None:
    target = Target(role="checkbox", name="Toggle Todo")

    change = observed_change(state("/", TODO_ADDED), state("/", TODO_DONE), Action(type="click"), target)

    assert change is not None and change.checked is not None
    assert [(c.role, c.name) for c in change.checked] == [("checkbox", "Toggle Todo")]


def test_a_new_page_records_its_path_without_the_query() -> None:
    change = observed_change(
        state("/", '- heading "Home"'),
        state("/wiki/Alan_Turing", '- heading "Alan Turing"', query="session=8f2a"),
        Action(type="click"),
        Target(role="link", name="Alan Turing"),
    )

    assert change is not None
    assert change.url_matches == "^/wiki/Alan_Turing$"
    assert change.visible and change.visible[0].name == "Alan Turing"
    assert change.absent and change.absent[0].name == "Home"


def test_a_search_on_the_same_path_records_the_query() -> None:
    change = observed_change(
        state("/search", '- heading "Search"'),
        state("/search", '- heading "Search"', query="query=Bengaluru"),
        Action(type="click"),
        Target(role="button", name="Go"),
    )

    assert change is not None and change.url_matches == r"^/search\?query=Bengaluru$"


@pytest.mark.parametrize(
    ("before", "after", "expected", "replayed"),
    [
        # #482: Trello's new board; the replay made another board with another ID and name.
        (
            "/u/someone/boards",
            "/b/ff6N6zDd/reading-list",
            r"^/b/[^/]+/[^/]+$",
            "/b/W9yq3rpz/reading-list-r606",
        ),
        # A new issue gets the next number.
        ("/o/r/issues/new", "/o/r/issues/2", r"^/o/r/issues/\d+$", "/o/r/issues/3"),
        # Segments that didn't change stay exact: the docs' version, a page's own name.
        ("/3/", "/3/library/asyncio.html", r"^/3/library/asyncio\.html$", None),
        ("/", "/wiki/Alan_Turing", r"^/wiki/Alan_Turing$", None),
        ("/", "/package/express", r"^/package/express$", None),
    ],
)
def test_ids_a_site_makes_up_are_left_open(
    before: str, after: str, expected: str, replayed: str | None
) -> None:
    change = observed_change(
        state(before, '- heading "Before"'), state(after, '- heading "After"'), Action(type="click"),
        Target(role="button", name="Create"),
    )  # fmt: skip

    assert change is not None and change.url_matches == expected
    assert re.search(expected, after)
    if replayed is not None:
        assert re.search(expected, replayed)


def test_nothing_changed_gives_none() -> None:
    same = state("/", TODO_ADDED)
    assert observed_change(same, same, Action(type="click"), Target(role="button", name="Delete")) is None


def test_the_recorded_state_verifies_the_page_it_came_from() -> None:
    # A replay checks a step against what really happened: the change must pass the normal verifier.
    after = state("/search", TODO_ADDED, query="q=milk")
    change = observed_change(
        state("/search", TODO_TYPED), after, Action(type="press", value="Enter"), Target(role="textbox")
    )

    assert change is not None
    assert RuleVerifier().verify(change, after).verified
    assert not RuleVerifier().verify(change, state("/search", TODO_TYPED)).verified
    assert isinstance(change, ExpectedState)


def test_a_dialog_with_a_new_field_is_a_change() -> None:
    # MDN: "Search the site" opens a dialog whose only named element is a combobox (Phase 7, #470).
    before = state("/en-US/", '- banner:\n  - button "Search the site"\n- main:\n  - heading "MDN"')
    after = state(
        "/en-US/",
        before.aria_excerpt + '\n- dialog:\n  - combobox "Search"\n  - status\n  - listbox "Search results"',
    )

    change = observed_change(
        before, after, Action(type="click"), Target(role="button", name="Search the site")
    )

    assert change is not None and change.visible is not None
    assert {(v.role, v.name) for v in change.visible} == {
        ("combobox", "Search"),
        ("listbox", "Search results"),
    }
