"""The web client's types are generated from web/openapi.json. If the API schema changes, regenerate it:
python -m promptgraphify.api.openapi > web/openapi.json && (cd web && npm run gen:api)"""

import json
from pathlib import Path

from promptgraphify.api.openapi import build

WEB = Path(__file__).parent.parent / "web"


def test_committed_openapi_matches_the_running_api():
    committed = json.loads((WEB / "openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build())), (
        "web/openapi.json is stale: regenerate it (see module docstring)"
    )


def test_generated_typescript_mentions_every_schema():
    ts = (WEB / "src" / "lib" / "api-types.ts").read_text(encoding="utf-8")
    for name in build()["components"]["schemas"]:
        assert name in ts, f"{name} missing from api-types.ts; run `npm run gen:api`"


def test_all_response_fields_are_required_in_the_schema():
    schemas = build()["components"]["schemas"]
    for name in ("GraphDocument", "Node", "Edge", "Diagnostic", "SourceCoverage", "DagView"):
        props = set(schemas[name]["properties"])
        assert props == set(schemas[name]["required"]), f"{name}: optional fields leak into the TypeScript types"
