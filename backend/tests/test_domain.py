"""CA-8 — tipos do domínio: total = free + locked e só Decimal (float recusado)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from analysis.domain import Balance, FeeInfo


def test_quantidade_total_do_saldo_e_free_mais_locked() -> None:
    saldo = Balance(asset="BTC", free=Decimal("0.3"), locked=Decimal("0.2"))

    assert saldo.total == Decimal("0.5")
    assert type(saldo.total) is Decimal


@pytest.mark.parametrize(
    "free, locked",
    [(0.1, Decimal("0")), (Decimal("0"), 0.1)],
    ids=["free-float", "locked-float"],
)
def test_saldo_recusa_float(free: object, locked: object) -> None:
    with pytest.raises(TypeError):
        Balance(asset="BTC", free=free, locked=locked)  # type: ignore[arg-type]


def test_taxas_recusam_float() -> None:
    with pytest.raises(TypeError):
        FeeInfo(
            maker=0.001,  # type: ignore[arg-type]
            taker=Decimal("0.001"),
            bnb_discount_enabled=True,
            bnb_discount_multiplier=Decimal("0.75"),
        )
