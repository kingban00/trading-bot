"""CA-25 — quantização nomeada com ROUND_HALF_EVEN."""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from analysis.money import (
    ASSET_QUANTITY_DECIMALS,
    PERCENT_DECIMALS,
    ROUNDING,
    USDT_DECIMALS,
    quantize_percent,
    quantize_quantity,
    quantize_usdt,
)


def test_constantes_de_quantizacao_sao_as_do_criterio() -> None:
    assert USDT_DECIMALS == 2
    assert PERCENT_DECIMALS == 2
    assert ASSET_QUANTITY_DECIMALS == 8
    assert ROUNDING == ROUND_HALF_EVEN


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2.345", "2.34"),
        ("2.355", "2.36"),
        ("2.3451", "2.35"),
        ("-2.345", "-2.34"),
        ("10", "10.00"),
    ],
)
def test_quantize_usdt_usa_duas_casas_com_half_even(value: str, expected: str) -> None:
    result = quantize_usdt(Decimal(value))

    assert str(result) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("12.125", "12.12"), ("12.135", "12.14"), ("100", "100.00")],
)
def test_quantize_percent_usa_duas_casas_com_half_even(value: str, expected: str) -> None:
    result = quantize_percent(Decimal(value))

    assert str(result) == expected


@pytest.mark.parametrize(
    "value, decimals, expected",
    [
        ("0.123456785", 8, "0.12345678"),
        ("0.123456775", 8, "0.12345678"),
        ("2.5", 0, "2"),
        ("3.5", 0, "4"),
        ("1.23456", 3, "1.235"),
    ],
)
def test_quantize_quantity_usa_a_precisao_do_ativo_com_half_even(
    value: str, decimals: int, expected: str
) -> None:
    result = quantize_quantity(Decimal(value), decimals)

    assert str(result) == expected


def test_quantize_quantity_usa_oito_casas_por_padrao() -> None:
    result = quantize_quantity(Decimal("0.123456785"))

    assert str(result) == "0.12345678"


@pytest.mark.parametrize("quantizer", [quantize_usdt, quantize_percent, quantize_quantity])
def test_quantizadores_recusam_float(quantizer: object) -> None:
    with pytest.raises(TypeError):
        quantizer(2.345)  # type: ignore[operator]
