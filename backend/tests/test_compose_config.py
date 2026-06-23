import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_declares_required_services():
    text = ROOT.joinpath("docker-compose.yml").read_text(encoding="utf-8")

    for service in ["frontend", "backend", "worker", "postgres", "redis", "minio"]:
        assert f"{service}:" in text


def test_local_compose_exposes_development_ports():
    text = ROOT.joinpath("docker-compose.yml").read_text(encoding="utf-8")

    for port in ['"3000:3000"', '"8000:8000"', '"5432:5432"', '"6379:6379"', '"9000:9000"', '"9001:9001"']:
        assert port in text

    assert "NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}" in text
    assert "CORS_ALLOW_ORIGINS: ${CORS_ALLOW_ORIGINS:-http://localhost:3000}" in text


def test_prod_compose_clears_internal_service_ports_and_uses_nginx_api_path():
    text = ROOT.joinpath("docker-compose.prod.yml").read_text(encoding="utf-8")

    for service in ["backend", "frontend", "postgres", "redis", "minio"]:
        match = re.search(rf"(?ms)^  {service}:\n(.*?)(?=^  \S|\Z)", text)
        assert match is not None
        block = match.group(0)
        assert "ports: !reset []" in block

    assert "NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-/api}" in text
