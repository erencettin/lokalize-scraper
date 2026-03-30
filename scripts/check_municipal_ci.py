"""Lightweight compile+import checks for municipal web provider."""

from __future__ import annotations

import py_compile
from pathlib import Path


def compile_tree(root: Path) -> None:
    for path in root.rglob("*.py"):
        py_compile.compile(path, doraise=True)


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    compile_tree(base / "providers" / "municipal_web")
    compile_tree(base / "tests" / "providers" / "municipal_web")

    from providers.municipal_web import MunicipalWebProvider  # noqa: F401
    from providers.municipal_web.provider import MunicipalWebProvider as FromModule  # noqa: F401

    print("municipal_web compile+import checks passed")


if __name__ == "__main__":
    main()
