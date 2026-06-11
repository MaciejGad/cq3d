import pytest

flask = pytest.importorskip("flask")

from cq3d_server import app, load_keyword_config


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_keyword_config_contains_current_dsl_terms():
    config = load_keyword_config()
    assert "box" in config["keywords"]
    assert "cylinder" in config["keywords"]
    assert "combine" in config["keywords"]
    assert "radius" in config["properties"]
    assert "min" in config["functions"]
    assert "step" in config["values"]


def test_compile_endpoint_returns_preview_and_bbox(client):
    response = client.post(
        "/api/compile",
        json={
            "source": """
model demo
unit mm

box body
  size 10 20 30
  at 0 0 0
end
""",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["error"] is None
    assert payload["final_object_id"] == "body"
    assert payload["preview_url"].endswith(".stl")
    assert payload["bbox"]["xlen"] == pytest.approx(10.0)


def test_export_step_endpoint_returns_step_file(client):
    response = client.post(
        "/api/export/step",
        json={
            "source": """
model demo
unit mm

box body
  size 10 20 30
end
""",
            "filename": "demo",
        },
    )

    assert response.status_code == 200
    assert response.headers["Content-Disposition"].endswith('demo.step"') or "demo.step" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"ISO-10303-21;")
