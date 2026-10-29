"""SPEC §16.6, D-112: FastAPI serves the built web app with a client-route fallback."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kairos_defense.api.app import create_app


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>Kairos Defense</title>")
    (d / "assets" / "app-123.js").write_text("console.log(1)")
    (d / "favicon.svg").write_text("<svg/>")
    return d


def test_root_serves_index(dist) -> None:
    c = TestClient(create_app(static_dir=dist))
    r = c.get("/")
    assert r.status_code == 200 and "<title>Kairos Defense</title>" in r.text


def test_spa_route_serves_index(dist) -> None:
    c = TestClient(create_app(static_dir=dist))
    for path in ("/live/DEMO-BRAVO-0828", "/cases", "/eval"):
        r = c.get(path)
        assert r.status_code == 200 and "Kairos Defense" in r.text, path


def test_api_404_is_json_not_index(dist) -> None:
    c = TestClient(create_app(static_dir=dist))
    for path in ("/api/nope", "/ws/x", "/assets/missing.js", "/missing.png"):
        r = c.get(path)
        assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_assets_served_with_type(dist) -> None:
    c = TestClient(create_app(static_dir=dist))
    r = c.get("/assets/app-123.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert "immutable" in r.headers["cache-control"]
    assert c.get("/favicon.svg").headers["content-type"].startswith("image/svg")
    assert c.get("/../../etc/passwd").status_code in (200, 404)  # never outside dist
    assert "root:" not in c.get("/..%2F..%2Fetc%2Fpasswd").text


def test_no_static_dir_is_api_only() -> None:
    c = TestClient(create_app())
    assert c.get("/").status_code == 404


def test_missing_index_refuses_to_mount(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="npm --prefix web run build"):
        create_app(static_dir=tmp_path)
