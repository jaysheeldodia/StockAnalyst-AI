from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_app_version() -> str:
    try:
        return version("stock-analyst")
    except PackageNotFoundError:
        return "0.1.0-dev"
