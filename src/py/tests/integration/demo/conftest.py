"""Give concurrent demo integration runs their own PostgreSQL container."""

from collections.abc import Generator

import psycopg
import pytest
from pytest_databases._service import DockerService, ServiceContainer
from pytest_databases.docker.postgres import PostgresService


@pytest.fixture(scope="session")
def postgres_service(docker_service: DockerService, postgres_image: str) -> Generator[PostgresService]:
    def check(service: ServiceContainer) -> bool:
        try:
            with psycopg.connect(
                host=service.host,
                port=service.port,
                user="postgres",
                password="demo-test-only",
                dbname="postgres",
                connect_timeout=3,
            ) as connection:
                return bool(connection.execute("SELECT 1").fetchone())
        except psycopg.OperationalError:
            return False

    with docker_service.run(
        image=postgres_image,
        check=check,
        container_host="127.0.0.1",
        container_port=5432,
        name="woheng-entry-postgres",
        env={"POSTGRES_PASSWORD": "demo-test-only"},
        exec_after_start="psql -U postgres -d postgres -c 'CREATE DATABASE pytest_databases;'",
        timeout=60,
        pause=0.5,
    ) as service:
        yield PostgresService(
            host=service.host,
            port=service.port,
            user="postgres",
            password="demo-test-only",
            database="pytest_databases",
        )
