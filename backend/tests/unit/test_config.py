from src.config import Settings


def test_defaults_load():
    s = Settings()
    assert s.jwt_algorithm == "ES256"
    assert s.app_env == "dev"
    assert s.jwt_access_token_expire_minutes == 15
    assert s.jwt_refresh_token_expire_days == 30
