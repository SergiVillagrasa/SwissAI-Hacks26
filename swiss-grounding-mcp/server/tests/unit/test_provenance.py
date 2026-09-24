from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.evidence.provenance import build_provenance


def test_build_provenance_uses_source_url_from_settings_and_given_timestamp():
    settings = Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})
    retrieved_at = datetime(2026, 9, 24, 18, 3, 12, tzinfo=timezone.utc)

    provenance = build_provenance(settings, retrieved_at=retrieved_at)

    assert provenance.source == "opentransportdata.swiss OJP 2.0"
    assert provenance.source_url == "https://example.test/ojp20"
    assert provenance.retrieved_at == "2026-09-24T18:03:12Z"


def test_build_provenance_defaults_retrieved_at_to_now():
    settings = Settings.from_env({})

    provenance = build_provenance(settings)

    assert provenance.retrieved_at.endswith("Z")
