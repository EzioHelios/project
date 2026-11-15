"""Isolate energy HTTP tests from concurrently running domain test sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pytest_databases.docker.postgres import PostgresService

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_databases._service import DockerService, ServiceContainer


@pytest.fixture(scope="session")
def postgres_service(docker_service: DockerService, postgres_image: str) -> Generator[PostgresService, None, None]:
    import psycopg

    password = "energy-entry-test"

    def ready(service: ServiceContainer) -> bool:
        try:
            with psycopg.connect(
                host=service.host,
                port=service.port,
                user="postgres",
                password=password,
                dbname="postgres",
                connect_timeout=5,
            ) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except psycopg.Error:
            return False

    with docker_service.run(
        image=postgres_image,
        name=f"energy_entry_{uuid4().hex[:8]}",
        container_host="127.0.0.1",
        container_port=5432,
        env={"POSTGRES_PASSWORD": password},
        check=ready,
        timeout=60,
        pause=0.5,
    ) as service:
        yield PostgresService(
            host=service.host, port=service.port, user="postgres", password=password, database="postgres"
        )
