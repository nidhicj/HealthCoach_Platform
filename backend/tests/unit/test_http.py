from src.lib.http import make_http_client


def test_user_agent_set():
    client = make_http_client()
    ua = client.headers["user-agent"]
    assert ua.startswith("parivarthan-backend/")


def test_caller_headers_merged():
    client = make_http_client(headers={"X-Custom": "yes"})
    assert client.headers["X-Custom"] == "yes"
    assert "parivarthan-backend" in client.headers["user-agent"]
