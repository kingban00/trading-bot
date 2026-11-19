"""Núcleo puro da carteira.

CA-8 (valor em USDT), CA-9 (par inverso / sem cotação), CA-10 (Earn),
CA-11 (poeira), CA-12 (saldo operável), CA-13 (concentração),
CA-14 (parados) e CA-16 (seleção dos pares consultados).
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal

from analysis.domain import AssetValuation, Balance, PricingSource
from analysis.portfolio import (
    CONCENTRATION_THRESHOLD_PERCENT,
    DEFAULT_WINDOW_DAYS,
    DUST_THRESHOLD_USDT,
    MAX_TRADE_SYMBOLS,
    concentration,
    find_stale_assets,
    is_earn_token,
    operable_balance,
    select_trade_symbols,
    total_equity,
    value_balances,
)
from tests.fakes import (
    DEFAULT_BALANCES,
    DEFAULT_TRADE_SYMBOLS,
    FIXED_NOW,
    balance,
    default_prices,
    make_trade,
    prices,
)


def by_asset(*balances: Balance, quotes: Mapping[str, Decimal] | None = None) -> dict[str, AssetValuation]:
    return {v.asset: v for v in value_balances(balances, quotes or {})}


# --------------------------------------------------------------------------
# Constantes do G1
# --------------------------------------------------------------------------


def test_limiares_e_janela_sao_os_decididos_no_g1() -> None:
    assert DUST_THRESHOLD_USDT == Decimal("5")
    assert CONCENTRATION_THRESHOLD_PERCENT == Decimal("25")
    assert DEFAULT_WINDOW_DAYS == 90


# --------------------------------------------------------------------------
# CA-8 — valor em USDT
# --------------------------------------------------------------------------


def test_valor_em_usdt_e_quantidade_total_vezes_preco_do_par_direto() -> None:
    valuations = by_asset(balance("BTC", "0.3", "0.2"), quotes=prices(BTCUSDT="100"))

    btc = valuations["BTC"]
    assert btc.total == Decimal("0.5")
    assert btc.price_usdt == Decimal("100")
    assert btc.value_usdt == Decimal("50")
    assert btc.pricing is PricingSource.DIRECT


def test_usdt_vale_um() -> None:
    valuations = by_asset(balance("USDT", "10", "5"))

    usdt = valuations["USDT"]
    assert usdt.price_usdt == Decimal("1")
    assert usdt.value_usdt == Decimal("15")
    assert usdt.pricing is PricingSource.USDT


def test_valores_da_avaliacao_sao_decimal() -> None:
    valuations = by_asset(balance("BTC", "0.3"), balance("USDT", "1"), quotes=prices(BTCUSDT="100"))

    for valuation in valuations.values():
        assert type(valuation.total) is Decimal
        assert type(valuation.price_usdt) is Decimal
        assert type(valuation.value_usdt) is Decimal


# --------------------------------------------------------------------------
# CA-9 — par inverso e sem cotação
# --------------------------------------------------------------------------


def test_par_inverso_e_avaliado_pelo_inverso_do_preco() -> None:
    valuations = by_asset(balance("BRL", "100"), quotes=prices(USDTBRL="5"))

    brl = valuations["BRL"]
    assert brl.value_usdt == Decimal("20")
    assert brl.pricing is PricingSource.INVERSE


def test_par_direto_tem_preferencia_sobre_o_inverso() -> None:
    valuations = by_asset(balance("EUR", "10"), quotes=prices(EURUSDT="1.1", USDTEUR="0.5"))

    eur = valuations["EUR"]
    assert eur.pricing is PricingSource.DIRECT
    assert eur.value_usdt == Decimal("11.0")


def test_ativo_sem_nenhum_par_fica_sem_cotacao_sem_excecao() -> None:
    valuations = by_asset(balance("XYZ", "7"))

    xyz = valuations["XYZ"]
    assert xyz.pricing is PricingSource.UNPRICED
    assert xyz.price_usdt is None
    assert xyz.value_usdt is None


def test_ativo_sem_cotacao_fica_fora_do_patrimonio_total() -> None:
    valuations = value_balances(
        (balance("USDT", "10"), balance("XYZ", "7")), {}
    )

    assert total_equity(valuations) == Decimal("10")


def test_preco_zero_e_tratado_como_sem_cotacao() -> None:
    valuations = by_asset(
        balance("BRL", "100"),
        balance("OLD", "3"),
        quotes=prices(USDTBRL="0", OLDUSDT="0.00000000"),
    )

    assert valuations["BRL"].pricing is PricingSource.UNPRICED
    assert valuations["OLD"].pricing is PricingSource.UNPRICED


# --------------------------------------------------------------------------
# CA-10 — tokens de Earn
# --------------------------------------------------------------------------


def test_token_com_prefixo_ld_e_reconhecido_como_earn() -> None:
    assert is_earn_token("LDBTC", prices(BTCUSDT="100")) is True


def test_ativo_com_par_usdt_proprio_nao_e_earn_mesmo_comecando_com_ld() -> None:
    assert is_earn_token("LDO", prices(LDOUSDT="2")) is False


def test_token_earn_e_avaliado_pelo_ativo_subjacente() -> None:
    valuations = by_asset(balance("LDBTC", "0.5"), quotes=prices(BTCUSDT="100"))

    ldbtc = valuations["LDBTC"]
    assert ldbtc.is_earn is True
    assert ldbtc.value_usdt == Decimal("50")


# --------------------------------------------------------------------------
# CA-11 — poeira
# --------------------------------------------------------------------------


def test_ativo_abaixo_do_limiar_e_poeira() -> None:
    valuations = by_asset(balance("DOGE", "49.9"), quotes=prices(DOGEUSDT="0.1"))

    assert valuations["DOGE"].is_dust is True


def test_ativo_exatamente_no_limiar_nao_e_poeira() -> None:
    valuations = by_asset(balance("DOGE", "50"), quotes=prices(DOGEUSDT="0.1"))

    assert valuations["DOGE"].is_dust is False


def test_usdt_nunca_e_poeira() -> None:
    valuations = by_asset(balance("USDT", "1"))

    assert valuations["USDT"].is_dust is False


def test_ativo_sem_cotacao_nao_e_poeira() -> None:
    valuations = by_asset(balance("XYZ", "0.001"))

    assert valuations["XYZ"].is_dust is False


# --------------------------------------------------------------------------
# CA-12 — saldo operável
# --------------------------------------------------------------------------


def test_saldo_operavel_e_somente_o_usdt_livre() -> None:
    balances = (
        balance("USDT", "100", "30"),
        balance("LDUSDT", "50"),
        balance("BTC", "1"),
    )

    assert operable_balance(balances) == Decimal("100")


def test_saldo_operavel_sem_usdt_e_zero() -> None:
    assert operable_balance((balance("BTC", "1"),)) == Decimal("0")


# --------------------------------------------------------------------------
# CA-13 — concentração
# --------------------------------------------------------------------------


def test_percentuais_de_concentracao_somam_cem_por_cento() -> None:
    valuations = value_balances(
        (balance("AAA", "10"), balance("BBB", "10"), balance("CCC", "10")),
        prices(AAAUSDT="1", BBBUSDT="1", CCCUSDT="1"),
    )

    entries = concentration(valuations)

    assert abs(sum(e.percent for e in entries) - Decimal("100")) <= Decimal("0.0001")


def test_concentracao_em_ordem_decrescente_de_valor() -> None:
    valuations = value_balances(
        (balance("AAA", "10"), balance("BBB", "30"), balance("CCC", "20")),
        prices(AAAUSDT="1", BBBUSDT="1", CCCUSDT="1"),
    )

    entries = concentration(valuations)

    assert [e.asset for e in entries] == ["BBB", "CCC", "AAA"]


def test_ativo_acima_do_limiar_e_sinalizado_e_no_limiar_nao() -> None:
    valuations = value_balances(
        (balance("BTC", "0.75"), balance("ETH", "0.25")),
        prices(BTCUSDT="100", ETHUSDT="100"),
    )

    entries = {e.asset: e for e in concentration(valuations)}

    assert entries["BTC"].percent == Decimal("75")
    assert entries["BTC"].flagged is True
    assert entries["ETH"].percent == Decimal("25")
    assert entries["ETH"].flagged is False


def test_poeira_nunca_e_sinalizada_na_concentracao() -> None:
    valuations = value_balances(
        (balance("DOGE", "40"), balance("XRP", "60")),
        prices(DOGEUSDT="0.1", XRPUSDT="0.1"),
    )

    entries = {e.asset: e for e in concentration(valuations)}

    assert entries["DOGE"].percent == Decimal("40")
    assert entries["DOGE"].flagged is False
    assert entries["XRP"].flagged is True


def test_usdt_nao_e_sinalizado_na_concentracao() -> None:
    valuations = value_balances(
        (balance("USDT", "80"), balance("BTC", "0.2")),
        prices(BTCUSDT="100"),
    )

    entries = {e.asset: e for e in concentration(valuations)}

    assert entries["USDT"].flagged is False


def test_ativo_sem_cotacao_fica_fora_da_concentracao() -> None:
    valuations = value_balances((balance("USDT", "10"), balance("XYZ", "7")), {})

    assert [e.asset for e in concentration(valuations)] == ["USDT"]


def test_carteira_sem_valor_cotado_tem_concentracao_vazia() -> None:
    valuations = value_balances((balance("XYZ", "7"),), {})

    assert concentration(valuations) == ()


# --------------------------------------------------------------------------
# CA-14 — ativos parados (relógio injetado, janela nos dois lados)
# --------------------------------------------------------------------------


def stale(*balances: Balance, trades=(), quotes: Mapping[str, Decimal] | None = None) -> tuple[str, ...]:
    valuations = value_balances(balances, quotes if quotes is not None else prices(BTCUSDT="100"))
    return find_stale_assets(valuations, trades, now=FIXED_NOW, window_days=DEFAULT_WINDOW_DAYS)


def test_ativo_com_trade_exatamente_no_limite_da_janela_nao_e_parado() -> None:
    limit = FIXED_NOW - timedelta(days=DEFAULT_WINDOW_DAYS)

    result = stale(balance("BTC", "1"), trades=[make_trade("BTCUSDT", executed_at=limit)])

    assert result == ()


def test_ativo_com_trade_um_segundo_antes_da_janela_e_parado() -> None:
    outside = FIXED_NOW - timedelta(days=DEFAULT_WINDOW_DAYS, seconds=1)

    result = stale(balance("BTC", "1"), trades=[make_trade("BTCUSDT", executed_at=outside)])

    assert result == ("BTC",)


def test_ativo_sem_trade_na_janela_e_parado() -> None:
    assert stale(balance("BTC", "1")) == ("BTC",)


def test_poeira_nao_e_parada() -> None:
    assert stale(balance("BTC", "0.01")) == ()


def test_usdt_nao_e_parado() -> None:
    assert stale(balance("USDT", "1000")) == ()


def test_token_earn_nao_e_parado() -> None:
    assert stale(balance("LDBTC", "1")) == ()


def test_ativo_sem_cotacao_nao_e_parado() -> None:
    assert stale(balance("XYZ", "1000")) == ()


def test_ativo_cotado_so_por_par_inverso_nao_e_avaliado_como_parado() -> None:
    assert stale(balance("BRL", "1000"), quotes=prices(USDTBRL="5")) == ()


def test_parados_saem_em_ordem_alfabetica() -> None:
    quotes = prices(ETHUSDT="100", ADAUSDT="100", SOLUSDT="100")

    result = stale(balance("SOL", "1"), balance("ADA", "1"), balance("ETH", "1"), quotes=quotes)

    assert result == ("ADA", "ETH", "SOL")


# --------------------------------------------------------------------------
# CA-16 — pares consultados no histórico
# --------------------------------------------------------------------------


def test_historico_so_para_pares_usdt_diretos_de_ativos_relevantes() -> None:
    valuations = value_balances(DEFAULT_BALANCES, default_prices())

    symbols = select_trade_symbols(valuations)

    assert sorted(symbols) == list(DEFAULT_TRADE_SYMBOLS)
    assert len(symbols) == len(set(symbols))


def test_quantidade_de_pares_consultados_e_limitada_aos_de_maior_valor() -> None:
    count = MAX_TRADE_SYMBOLS + 5
    balances = tuple(balance(f"A{i:03d}", "10") for i in range(1, count + 1))
    quotes = {f"A{i:03d}USDT": Decimal(i) for i in range(1, count + 1)}
    valuations = value_balances(balances, quotes)

    symbols = select_trade_symbols(valuations)

    expected = {f"A{i:03d}USDT" for i in range(count - MAX_TRADE_SYMBOLS + 1, count + 1)}
    assert len(symbols) == MAX_TRADE_SYMBOLS
    assert set(symbols) == expected
