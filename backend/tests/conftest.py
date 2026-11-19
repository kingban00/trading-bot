"""Configuração comum do pytest da Fase 0.

Sem imports de produção aqui: se um módulo de produção ainda não existir, a
falha aparece na coleta de cada arquivo de teste (motivo esperado do "red"),
e não no carregamento do conftest.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    """Diretório de relatórios ainda inexistente; o `main` deve criá-lo."""
    return tmp_path / "reports"
