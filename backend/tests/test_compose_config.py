from pathlib import Path


def test_compose_declares_required_services():
    text = Path(__file__).resolve().parents[2].joinpath("docker-compose.yml").read_text(encoding="utf-8")

    for service in ["frontend", "backend", "worker", "postgres", "redis", "minio"]:
        assert f"{service}:" in text


def test_compose_supports_lan_host_for_frontend_and_cors():
    text = Path(__file__).resolve().parents[2].joinpath("docker-compose.yml").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_BASE_URL: http://${LAN_HOST:-localhost}:8000" in text
    assert "CORS_ALLOW_ORIGINS: http://localhost:3000,http://${LAN_HOST:-localhost}:3000" in text
