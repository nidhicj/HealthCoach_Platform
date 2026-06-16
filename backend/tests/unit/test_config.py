from src.config import Settings


def test_defaults_load():
    s = Settings()
    assert s.jwt_algorithm == "ES256"
    assert s.app_env == "dev"
    assert s.jwt_access_token_expire_minutes == 15
    assert s.jwt_refresh_token_expire_days == 30


def test_scheduler_secret_defaults_to_empty_string():
    s = Settings(scheduler_secret="")
    assert s.scheduler_secret == ""


def test_scheduler_secret_accepts_value():
    s = Settings(scheduler_secret="super-secret-token")
    assert s.scheduler_secret == "super-secret-token"
