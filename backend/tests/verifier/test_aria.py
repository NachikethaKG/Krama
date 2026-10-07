from pathlib import Path

from app.verifier import parse_aria_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_roles_names_values_and_attributes() -> None:
    snapshot = "\n".join(
        [
            '- main "New Repository":',
            '  - heading "New Repository" [level=3]',
            "  - paragraph: The repository name is already used.",
            '  - textbox "Repository Name *": demo-repo',
            '  - checkbox "Initialize Repository" [checked]',
            '  - checkbox "Make repository private"',
            '  - checkbox "Mixed" [checked=mixed]',
            '  - link "Migrate repository.":',
            "    - /url: /repo/migrate",
            '  - button "Say \\"hi\\""',
        ]
    )

    nodes = parse_aria_snapshot(snapshot)

    assert [n.role for n in nodes] == [
        "main", "heading", "paragraph", "textbox", "checkbox", "checkbox", "checkbox", "link", "button"
    ]  # fmt: skip
    heading, paragraph, textbox, checked, unchecked, mixed = nodes[1:7]
    assert heading.attrs == {"level": "3"}
    assert paragraph.name == "" and paragraph.label() == "The repository name is already used."
    assert textbox.name == "Repository Name *" and textbox.value == "demo-repo"
    assert checked.checked and not unchecked.checked and not mixed.checked
    assert nodes[-1].name == 'Say "hi"'


def test_parses_every_real_gitea_snapshot() -> None:
    for f in FIXTURES.glob("*.aria.yaml"):
        nodes = parse_aria_snapshot(f.read_text(encoding="utf-8"))
        assert nodes, f.name
        assert nodes[0].role == "main"
        assert not any(n.role.startswith("/") for n in nodes)
