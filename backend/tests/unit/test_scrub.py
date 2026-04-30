from src.telemetry.scrub import scrub


def test_scrub_email_key():
    event = {"extra": {"email": "user@example.com", "note": "hello"}}
    result = scrub(event)
    assert result["extra"]["email"] == "<redacted>"
    assert result["extra"]["note"] == "hello"


def test_scrub_jwt_in_string():
    event = {"message": "token eyJhbGciOiJFUzI1NiJ9.payload.signature used"}
    result = scrub(event)
    assert "eyJ" not in result["message"]
    assert "<jwt_redacted>" in result["message"]


def test_scrub_authorization_header():
    event = {"request": {"headers": {"authorization": "Bearer secret-token"}}}
    result = scrub(event)
    assert result["request"]["headers"]["authorization"] == "<redacted>"


def test_scrub_ip_truncation_ipv4():
    event = {"ip": "192.168.1.100"}
    result = scrub(event)
    assert result["ip"] == "192.168.1.0"


def test_scrub_nested_transcript():
    event = {"data": {"transcript_content": "Patient said they feel stressed"}}
    result = scrub(event)
    assert result["data"]["transcript_content"] == "<redacted>"


def test_scrub_leaves_safe_fields():
    event = {"user_id": "abc-uuid", "hc_id": "xyz-uuid", "ms": 42}
    result = scrub(event)
    assert result["user_id"] == "abc-uuid"
    assert result["hc_id"] == "xyz-uuid"
    assert result["ms"] == 42


def test_scrub_list():
    data = [{"email": "a@b.com"}, {"note": "safe"}]
    result = scrub(data)
    assert result[0]["email"] == "<redacted>"
    assert result[1]["note"] == "safe"
