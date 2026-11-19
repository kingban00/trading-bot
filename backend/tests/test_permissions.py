"""CA-2, CA-3 e CA-5 — avaliação pura das permissões da chave."""
from __future__ import annotations

import pytest

from analysis.domain import WarningCode
from analysis.permissions import FORBIDDEN_PERMISSIONS, evaluate_permissions
from tests.fakes import read_only_permissions

FORBIDDEN_IN_CRITERIA = (
    "enableSpotAndMarginTrading",
    "enableWithdrawals",
    "enableInternalTransfer",
    "permitsUniversalTransfer",
    "enableMargin",
    "enableFutures",
    "enableVanillaOptions",
)


def test_lista_de_permissoes_proibidas_cobre_todas_as_do_criterio() -> None:
    assert set(FORBIDDEN_IN_CRITERIA) <= set(FORBIDDEN_PERMISSIONS)


def test_chave_somente_leitura_com_ip_restrito_e_aprovada_sem_avisos() -> None:
    verdict = evaluate_permissions(read_only_permissions(ip_restrict=True))

    assert verdict.approved is True
    assert verdict.forbidden == ()
    assert verdict.warnings == ()


@pytest.mark.parametrize("permission", FORBIDDEN_IN_CRITERIA)
def test_permissao_proibida_reprova_a_chave_e_e_nomeada(permission: str) -> None:
    verdict = evaluate_permissions(read_only_permissions(granted=[permission]))

    assert verdict.approved is False
    assert verdict.forbidden == (permission,)


def test_varias_permissoes_proibidas_sao_todas_listadas_em_ordem_alfabetica() -> None:
    granted = ["enableWithdrawals", "enableFutures", "enableSpotAndMarginTrading"]

    verdict = evaluate_permissions(read_only_permissions(granted=granted))

    assert verdict.forbidden == ("enableFutures", "enableSpotAndMarginTrading", "enableWithdrawals")


def test_leitura_desligada_reprova_a_chave() -> None:
    verdict = evaluate_permissions(read_only_permissions(enable_reading=False))

    assert verdict.approved is False
    assert verdict.reading_enabled is False
    assert verdict.forbidden == ()


def test_chave_sem_restricao_de_ip_e_aprovada_com_aviso() -> None:
    verdict = evaluate_permissions(read_only_permissions(ip_restrict=False))

    assert verdict.approved is True
    assert verdict.warnings == (WarningCode.IP_UNRESTRICTED,)
