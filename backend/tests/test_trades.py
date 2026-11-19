"""CA-15 — resumo puro dos trades recentes (a paginação é testada no adaptador)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from analysis.portfolio import DEFAULT_WINDOW_DAYS
from analysis.trades import summarize_trades
from tests.fakes import FIXED_NOW, make_trade, prices

WINDOW_START = FIXED_NOW - timedelta(days=DEFAULT_WINDOW_DAYS)


def summarize(trades, quotes=None):
    return summarize_trades(
        trades,
        quotes if quotes is not None else prices(BNBUSDT="600"),
        now=FIXED_NOW,
        window_days=DEFAULT_WINDOW_DAYS,
    )


def test_resumo_conta_trades_e_soma_volume_em_usdt() -> None:
    trades = [
        make_trade("BTCUSDT", trade_id=1, quote_quantity="100.50"),
        make_trade("ETHUSDT", trade_id=2, quote_quantity="49.50"),
    ]

    summary = summarize(trades)

    assert summary.trade_count == 2
    assert summary.volume_usdt == Decimal("150.00")


def test_trade_no_limite_da_janela_entra_e_um_segundo_antes_fica_fora() -> None:
    trades = [
        make_trade(trade_id=1, quote_quantity="10", executed_at=WINDOW_START),
        make_trade(trade_id=2, quote_quantity="99", executed_at=WINDOW_START - timedelta(seconds=1)),
    ]

    summary = summarize(trades)

    assert summary.trade_count == 1
    assert summary.volume_usdt == Decimal("10")


def test_taxas_sao_agrupadas_por_ativo_de_comissao() -> None:
    trades = [
        make_trade(trade_id=1, commission="0.001", commission_asset="BNB"),
        make_trade(trade_id=2, commission="0.002", commission_asset="BNB"),
        make_trade(trade_id=3, commission="0.10", commission_asset="USDT"),
    ]

    summary = summarize(trades)

    assert summary.fees_by_asset == {"BNB": Decimal("0.003"), "USDT": Decimal("0.10")}


def test_taxas_sao_convertidas_para_usdt_pelo_preco_do_ativo() -> None:
    trades = [
        make_trade(trade_id=1, commission="0.003", commission_asset="BNB"),
        make_trade(trade_id=2, commission="0.10", commission_asset="USDT"),
    ]

    summary = summarize(trades, prices(BNBUSDT="600"))

    assert summary.fees_usdt_by_asset == {"BNB": Decimal("1.800"), "USDT": Decimal("0.10")}
    assert summary.total_fees_usdt == Decimal("1.90")


def test_taxa_em_ativo_sem_cotacao_fica_fora_do_total_sem_excecao() -> None:
    trades = [
        make_trade(trade_id=1, commission="5", commission_asset="XYZ"),
        make_trade(trade_id=2, commission="0.10", commission_asset="USDT"),
    ]

    summary = summarize(trades, {})

    assert summary.fees_by_asset["XYZ"] == Decimal("5")
    assert summary.unconverted_fee_assets == ("XYZ",)
    assert summary.total_fees_usdt == Decimal("0.10")


def test_taxas_fora_da_janela_sao_ignoradas() -> None:
    old = WINDOW_START - timedelta(days=1)
    trades = [make_trade(trade_id=1, commission="1", commission_asset="USDT", executed_at=old)]

    summary = summarize(trades)

    assert summary.fees_by_asset == {}
    assert summary.total_fees_usdt == Decimal("0")


def test_resumo_sem_trades_tem_zeros_em_decimal() -> None:
    summary = summarize([])

    assert summary.trade_count == 0
    assert summary.volume_usdt == Decimal("0")
    assert type(summary.volume_usdt) is Decimal
    assert type(summary.total_fees_usdt) is Decimal
