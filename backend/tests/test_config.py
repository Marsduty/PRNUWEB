from app.core.config import Settings


def test_cors_origins_are_parsed_from_comma_separated_config():
    settings = Settings(cors_allow_origins="http://localhost:3000, http://192.168.1.10:3000")

    assert settings.cors_origins == ["http://localhost:3000", "http://192.168.1.10:3000"]
