"""Guard the source tree against legacy, unscoped Qt enum aliases."""

import ast
from pathlib import Path


SRC_ROOT = Path(__file__).parents[1] / "src"

LEGACY_ENUM_MEMBERS = {
    "QAbstractSocket": {"ConnectedState"},
    "QAudioFormat": {"Int16"},
    "QFont": {"Bold"},
    "QMessageBox": {"No", "Yes"},
    "QPainter": {"Antialiasing"},
    "QSizePolicy": {"Expanding"},
    "Qt": {
        "AlignCenter",
        "NoBrush",
        "NoPen",
        "PointingHandCursor",
        "WA_StyledBackground",
        "WA_TranslucentBackground",
        "WA_TransparentForMouseEvents",
    },
}


def _source_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def test_qt_enums_use_scoped_pyside6_names() -> None:
    violations: list[str] = []

    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
                continue
            if node.attr in LEGACY_ENUM_MEMBERS.get(node.value.id, set()):
                relative_path = path.relative_to(SRC_ROOT.parent)
                violations.append(
                    f"{relative_path}:{node.lineno}: {node.value.id}.{node.attr}"
                )

    assert violations == []


def test_source_has_no_attr_defined_suppressions() -> None:
    marker = "# type: " + "ignore[attr-defined]"
    violations = [
        str(path.relative_to(SRC_ROOT.parent))
        for path in _source_files()
        if marker in path.read_text()
    ]

    assert violations == []
