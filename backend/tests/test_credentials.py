"""CA-1 (credenciais ausentes) e CA-6 (segredo fora do repr) — unidade pura."""
from __future__ import annotations

import pytest

from analysis.credentials import API_KEY_VAR, API_SECRET_VAR, Credentials, load_credentials
from analysis.errors import ConfigurationError, MissingCredentialsError
from tests.fakes import SENTINEL_API_KEY, SENTINEL_API_SECRET, SENTINEL_ENV


def test_nomes_das_variaveis_de_ambiente_sao_os_do_env_example() -> None:
    assert (API_KEY_VAR, API_SECRET_VAR) == ("BINANCE_API_KEY", "BINANCE_API_SECRET")


def test_load_credentials_le_chave_e_segredo_do_env_injetado() -> None:
    credentials = load_credentials(SENTINEL_ENV)

    assert credentials == Credentials(api_key=SENTINEL_API_KEY, api_secret=SENTINEL_API_SECRET)


@pytest.mark.parametrize(
    "env, missing",
    [
        ({}, ("BINANCE_API_KEY", "BINANCE_API_SECRET")),
        ({"BINANCE_API_KEY": "k"}, ("BINANCE_API_SECRET",)),
        ({"BINANCE_API_SECRET": "s"}, ("BINANCE_API_KEY",)),
        ({"BINANCE_API_KEY": "", "BINANCE_API_SECRET": "s"}, ("BINANCE_API_KEY",)),
        ({"BINANCE_API_KEY": "k", "BINANCE_API_SECRET": "   "}, ("BINANCE_API_SECRET",)),
    ],
    ids=["ambas-ausentes", "segredo-ausente", "chave-ausente", "chave-vazia", "segredo-so-espacos"],
)
def test_load_credentials_aponta_cada_variavel_ausente_ou_vazia(
    env: dict[str, str], missing: tuple[str, ...]
) -> None:
    with pytest.raises(MissingCredentialsError) as raised:
        load_credentials(env)

    assert raised.value.missing == missing


def test_mensagem_de_credenciais_ausentes_cita_as_variaveis() -> None:
    with pytest.raises(MissingCredentialsError) as raised:
        load_credentials({})

    assert "BINANCE_API_KEY" in str(raised.value)
    assert "BINANCE_API_SECRET" in str(raised.value)


def test_credenciais_ausentes_sao_um_erro_de_configuracao() -> None:
    assert issubclass(MissingCredentialsError, ConfigurationError)


def test_repr_e_str_das_credenciais_nao_expoem_chave_nem_segredo() -> None:
    credentials = Credentials(api_key=SENTINEL_API_KEY, api_secret=SENTINEL_API_SECRET)

    shown = repr(credentials) + str(credentials)

    assert SENTINEL_API_KEY not in shown
    assert SENTINEL_API_SECRET not in shown
