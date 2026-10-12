"""Browser resource permissions required by the tenant campus renderer."""

from app.lib.settings import AppSettings
from app.server.core import _build_csp


def test_campus_resources_have_narrow_csp_permissions() -> None:
    """Allow the configured imagery host and local model blobs, not arbitrary hosts."""
    policy = dict(directive.split(" ", 1) for directive in _build_csp(AppSettings()).split("; "))
    for directive in ("connect-src", "img-src"):
        sources = policy[directive].split()
        assert "https://server.arcgisonline.com" in sources
        assert "blob:" in sources
        assert "*" not in sources
        assert "https:" not in sources
    assert policy["object-src"] == "'none'"
    assert policy["frame-ancestors"] == "'none'"
    assert "blob:" not in policy["script-src"].split()
