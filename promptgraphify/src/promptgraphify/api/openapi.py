"""Print the OpenAPI document of the API (used to generate the web client's TypeScript types)."""

from __future__ import annotations

import json
import sys

from .app import create_app


def build() -> dict:
    return create_app().openapi()


def main() -> None:
    sys.stdout.write(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
