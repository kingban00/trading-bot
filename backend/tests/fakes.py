"""Fakes e utilitários dos testes da Fase 0 (análise da conta).

- As classes ``Fake*Reader``/``FakeMarketData`` implementam estruturalmente os
  Protocols de ``analysis.ports``. Não há mocks de detalhes internos.
- ``FakeExchange`` monta as cinco portas com um log de chamadas compartilhado
  e expõe ``factory(credentials)``, que é a ``ports_factory`` do ``main``.
- ``FakeCcxtBinance`` substitui o cliente ccxt dentro do adaptador
  ``exchange.binance_readonly`` e devolve o JSON bruto da Binance (strings
  para valores decimais, inteiros para ids e tempos em ms).
"""
from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from analysis.account_report import main
from analysis.credentials import Credentials
from analysis.domain import ApiKeyPermissions, Balance, FeeInfo, Trade
from analysis.ports import ReportPorts

FIXED_NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
EXPECTED_JSON_NAME = "account-report-20261119T120000Z.json"

SENTINEL_API_KEY = "SENTINELA-API-KEY-7f3c9a1e"
SENTINEL_API_SECRET = "SENTINELA-API-SECRET-b42d8e05"
SENTINEL_ENV: Mapping[str, str] = {
    "BINANCE_API_KEY": SENTINEL_API_KEY,
    "BINANCE_API_SECRET": SENTINEL_API_SECRET,
}
SECRET_MARKERS = (SENTINEL_API_KEY, SENTINEL_API_SECRET, "signature=")


def fixed_clock() -> datetime:
    return FIXED_NOW


# --------------------------------------------------------------------------
# Construtores de objetos do domínio
# --------------------------------------------------------------------------


def read_only_permissions(
    *,
    ip_restrict: bool = True,
    enable_reading: bool = True,
    granted: Sequence[str] = (),
) -> ApiKeyPermissions:
    return ApiKeyPermissions(
        enable_reading=enable_reading,
        ip_restrict=ip_restrict,
        granted=frozenset(granted),
    )


def balance(asset: str, free: str = "0", locked: str = "0") -> Balance:
    return Balance(asset=asset, free=Decimal(free), locked=Decimal(locked))


def prices(**by_symbol: str) -> dict[str, Decimal]:
    return {symbol: Decimal(price) for symbol, price in by_symbol.items()}


def make_trade(
    symbol: str = "BTCUSDT",
    *,
    trade_id: int = 1,
    price: str = "100",
    quantity: str = "1",
    quote_quantity: str | None = None,
    commission: str = "0",
    commission_asset: str = "USDT",
    executed_at: datetime = FIXED_NOW - timedelta(days=1),
    is_buyer: bool = True,
    is_maker: bool = False,
) -> Trade:
    quote = (
        Decimal(quote_quantity)
        if quote_quantity is not None
        else Decimal(price) * Decimal(quantity)
    )
    return Trade(
        symbol=symbol,
        trade_id=trade_id,
        price=Decimal(price),
        quantity=Decimal(quantity),
        quote_quantity=quote,
        commission=Decimal(commission),
        commission_asset=commission_asset,
        executed_at=executed_at,
        is_buyer=is_buyer,
        is_maker=is_maker,
    )


def standard_fees(*, discount_enabled: bool = True) -> FeeInfo:
    return FeeInfo(
        maker=Decimal("0.001"),
        taker=Decimal("0.001"),
        bnb_discount_enabled=discount_enabled,
        bnb_discount_multiplier=Decimal("0.75"),
    )


# Carteira padrão dos testes do relatório:
#   USDT 1000 livre + 50 travado  -> saldo operável 1000
#   BTC  0.01 x 50000 = 500       -> trade recente
#   ETH  0.1  x 3000  = 300       -> sem trade na janela (parado)
#   BNB  0.5  x 600   = 300       -> trade recente; saldo de BNB > 0
#   DOGE 10   x 0.1   = 1         -> poeira
#   LDUSDT 200                    -> token de Earn
#   BRL 100 / USDTBRL 5 = 20      -> par inverso
#   XYZ 7                         -> sem cotação
DEFAULT_BALANCES: tuple[Balance, ...] = (
    balance("USDT", "1000", "50"),
    balance("BTC", "0.01"),
    balance("ETH", "0.1"),
    balance("BNB", "0.5"),
    balance("DOGE", "10"),
    balance("LDUSDT", "200"),
    balance("BRL", "100"),
    balance("XYZ", "7"),
)
DEFAULT_PRICES: Mapping[str, str] = {
    "BTCUSDT": "50000",
    "ETHUSDT": "3000",
    "BNBUSDT": "600",
    "DOGEUSDT": "0.1",
    "USDTBRL": "5",
}
DEFAULT_TRADE_SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT")


def default_prices() -> dict[str, Decimal]:
    return prices(**DEFAULT_PRICES)


def default_trades_by_symbol() -> dict[str, tuple[Trade, ...]]:
    return {
        "BTCUSDT": (
            make_trade(
                "BTCUSDT",
                trade_id=11,
                price="50000",
                quantity="0.002",
                commission="0.0001",
                commission_asset="BNB",
                executed_at=FIXED_NOW - timedelta(days=10),
            ),
        ),
        "BNBUSDT": (
            make_trade(
                "BNBUSDT",
                trade_id=21,
                price="600",
                quantity="0.1",
                commission="0.06",
                commission_asset="USDT",
                executed_at=FIXED_NOW - timedelta(days=20),
            ),
        ),
    }


# --------------------------------------------------------------------------
# Fakes das portas (implementam os Protocols de analysis.ports)
# --------------------------------------------------------------------------


class _RecordingPort:
    def __init__(self, log: list[str], error: Exception | None) -> None:
        self._log = log
        self._error = error

    def _record(self, call: str) -> None:
        self._log.append(call)
        if self._error is not None:
            raise self._error


class FakeApiKeyPermissionReader(_RecordingPort):
    def __init__(
        self,
        permissions: ApiKeyPermissions,
        log: list[str],
        error: Exception | None = None,
    ) -> None:
        super().__init__(log, error)
        self._permissions = permissions

    def get_api_key_permissions(self) -> ApiKeyPermissions:
        self._record("get_api_key_permissions")
        return self._permissions


class FakeBalanceReader(_RecordingPort):
    def __init__(
        self,
        balances: Sequence[Balance],
        log: list[str],
        error: Exception | None = None,
    ) -> None:
        super().__init__(log, error)
        self._balances = tuple(balances)

    def get_balances(self) -> Sequence[Balance]:
        self._record("get_balances")
        return self._balances


class FakeMarketData(_RecordingPort):
    def __init__(
        self,
        prices_by_symbol: Mapping[str, Decimal],
        log: list[str],
        error: Exception | None = None,
    ) -> None:
        super().__init__(log, error)
        self._prices = dict(prices_by_symbol)

    def get_prices(self) -> Mapping[str, Decimal]:
        self._record("get_prices")
        return dict(self._prices)


class FakeTradeHistoryReader(_RecordingPort):
    def __init__(
        self,
        trades_by_symbol: Mapping[str, Sequence[Trade]],
        log: list[str],
        error: Exception | None = None,
    ) -> None:
        super().__init__(log, error)
        self._trades_by_symbol = {k: tuple(v) for k, v in trades_by_symbol.items()}
        self.requests: list[tuple[str, datetime]] = []

    def get_trades(self, symbol: str, since: datetime) -> Sequence[Trade]:
        self.requests.append((symbol, since))
        self._record(f"get_trades:{symbol}")
        return self._trades_by_symbol.get(symbol, ())


class FakeFeeReader(_RecordingPort):
    def __init__(
        self,
        fee_info: FeeInfo,
        log: list[str],
        error: Exception | None = None,
    ) -> None:
        super().__init__(log, error)
        self._fee_info = fee_info

    def get_fees(self) -> FeeInfo:
        self._record("get_fees")
        return self._fee_info


@dataclass
class FakeExchange:
    """Conjunto de portas fake com log de chamadas compartilhado.

    ``errors`` mapeia o nome do método da porta (ex.: ``"get_balances"``) para a
    exceção que ele deve levantar.
    """

    permissions: ApiKeyPermissions = field(default_factory=read_only_permissions)
    balances: Sequence[Balance] = DEFAULT_BALANCES
    prices: Mapping[str, Decimal] = field(default_factory=default_prices)
    trades_by_symbol: Mapping[str, Sequence[Trade]] = field(
        default_factory=default_trades_by_symbol
    )
    fee_info: FeeInfo = field(default_factory=standard_fees)
    errors: Mapping[str, Exception] = field(default_factory=dict)
    log: list[str] = field(default_factory=list, init=False)
    received_credentials: list[Credentials] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.permission_reader = FakeApiKeyPermissionReader(
            self.permissions, self.log, self.errors.get("get_api_key_permissions")
        )
        self.balance_reader = FakeBalanceReader(
            self.balances, self.log, self.errors.get("get_balances")
        )
        self.market_data = FakeMarketData(
            self.prices, self.log, self.errors.get("get_prices")
        )
        self.trade_reader = FakeTradeHistoryReader(
            self.trades_by_symbol, self.log, self.errors.get("get_trades")
        )
        self.fee_reader = FakeFeeReader(
            self.fee_info, self.log, self.errors.get("get_fees")
        )

    def factory(self, credentials: Credentials) -> ReportPorts:
        self.received_credentials.append(credentials)
        return ReportPorts(
            permissions=self.permission_reader,
            balances=self.balance_reader,
            market_data=self.market_data,
            trade_history=self.trade_reader,
            fees=self.fee_reader,
        )


# --------------------------------------------------------------------------
# Execução do main com saída capturada
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportRun:
    exit_code: int
    stdout: str
    stderr: str
    reports_dir: Path

    def json_files(self) -> list[Path]:
        if not self.reports_dir.exists():
            return []
        return sorted(self.reports_dir.glob("*.json"))

    def json_report(self) -> dict[str, Any]:
        files = self.json_files()
        assert len(files) == 1, f"esperado 1 JSON em reports/, achados: {files}"
        return json.loads(files[0].read_text(encoding="utf-8"))

    def all_output(self) -> str:
        written = "".join(p.read_text(encoding="utf-8") for p in self.json_files())
        return self.stdout + self.stderr + written


def run_report(
    exchange: FakeExchange,
    reports_dir: Path,
    *,
    argv: Sequence[str] = (),
    env: Mapping[str, str] = SENTINEL_ENV,
) -> ReportRun:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        list(argv),
        env=env,
        ports_factory=exchange.factory,
        clock=fixed_clock,
        stdout=stdout,
        stderr=stderr,
        reports_dir=reports_dir,
    )
    return ReportRun(exit_code, stdout.getvalue(), stderr.getvalue(), reports_dir)


# --------------------------------------------------------------------------
# Fake do cliente ccxt (para o adaptador exchange.binance_readonly)
# --------------------------------------------------------------------------


def to_ms(moment: datetime) -> int:
    return int(moment.timestamp()) * 1000


def raw_api_restrictions(**overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "ipRestrict": True,
        "createTime": 1700000000000,
        "enableReading": True,
        "enableWithdrawals": False,
        "enableInternalTransfer": False,
        "enableMargin": False,
        "enableFutures": False,
        "permitsUniversalTransfer": False,
        "enableVanillaOptions": False,
        "enableSpotAndMarginTrading": False,
        "enablePortfolioMarginTrading": False,
    }
    raw.update(overrides)
    return raw


def raw_account(*rows: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "makerCommission": 10,
        "takerCommission": 10,
        "canTrade": False,
        "canWithdraw": False,
        "canDeposit": True,
        "accountType": "SPOT",
        "balances": [
            {"asset": asset, "free": free, "locked": locked}
            for asset, free, locked in rows
        ],
        "permissions": ["SPOT"],
    }


def raw_trade(
    trade_id: int,
    executed_at: datetime,
    *,
    symbol: str = "BTCUSDT",
    price: str = "50000.00000000",
    qty: str = "0.00100000",
    quote_qty: str = "50.00000000",
    commission: str = "0.00007500",
    commission_asset: str = "BNB",
    is_buyer: bool = True,
    is_maker: bool = False,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "id": trade_id,
        "orderId": 1000 + trade_id,
        "orderListId": -1,
        "price": price,
        "qty": qty,
        "quoteQty": quote_qty,
        "commission": commission,
        "commissionAsset": commission_asset,
        "time": to_ms(executed_at),
        "isBuyer": is_buyer,
        "isMaker": is_maker,
        "isBestMatch": True,
    }


def raw_commission(
    *,
    maker: str = "0.00100000",
    taker: str = "0.00100000",
    enabled_for_account: bool = True,
    enabled_for_symbol: bool = True,
    discount: str = "0.75000000",
) -> dict[str, Any]:
    zero = "0.00000000"
    return {
        "symbol": "BTCUSDT",
        "standardCommission": {"maker": maker, "taker": taker, "buyer": zero, "seller": zero},
        "taxCommission": {"maker": zero, "taker": zero, "buyer": zero, "seller": zero},
        "discount": {
            "enabledForAccount": enabled_for_account,
            "enabledForSymbol": enabled_for_symbol,
            "discountAsset": "BNB",
            "discount": discount,
        },
    }


class FakeCcxtBinance:
    """Substituto do ``ccxt.binance`` com os endpoints implícitos de leitura.

    Métodos (mesmos nomes do ccxt): ``sapi_get_account_apirestrictions``,
    ``private_get_account``, ``public_get_ticker_price``,
    ``private_get_mytrades`` e ``private_get_account_commission``.
    Se ``error`` for informado, toda chamada levanta essa exceção.
    """

    def __init__(
        self,
        *,
        api_restrictions: dict[str, Any] | None = None,
        account: dict[str, Any] | None = None,
        ticker_prices: list[dict[str, str]] | None = None,
        my_trades: Sequence[dict[str, Any]] = (),
        commission: dict[str, Any] | None = None,
        error: Exception | None = None,
        api_key: str = SENTINEL_API_KEY,
        secret: str = SENTINEL_API_SECRET,
    ) -> None:
        self.apiKey = api_key
        self.secret = secret
        self._api_restrictions = (
            api_restrictions if api_restrictions is not None else raw_api_restrictions()
        )
        self._account = account if account is not None else raw_account()
        self._ticker_prices = ticker_prices if ticker_prices is not None else []
        self._my_trades = sorted(my_trades, key=lambda row: row["id"])
        self._commission = commission if commission is not None else raw_commission()
        self._error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def calls_to(self, method: str) -> list[dict[str, Any]]:
        return [params for name, params in self.calls if name == method]

    def _record(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        received = dict(params or {})
        self.calls.append((method, received))
        if self._error is not None:
            raise self._error
        return received

    def sapi_get_account_apirestrictions(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("sapi_get_account_apirestrictions", params)
        return dict(self._api_restrictions)

    def private_get_account(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("private_get_account", params)
        return json.loads(json.dumps(self._account))

    def public_get_ticker_price(self, params: dict[str, Any] | None = None) -> list[dict[str, str]]:
        self._record("public_get_ticker_price", params)
        return [dict(row) for row in self._ticker_prices]

    def private_get_mytrades(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        received = self._record("private_get_mytrades", params)
        symbol = received["symbol"]
        limit = int(received.get("limit", 500))
        rows = [row for row in self._my_trades if row["symbol"] == symbol]
        if "fromId" in received:
            from_id = int(received["fromId"])
            return [dict(r) for r in rows if r["id"] >= from_id][:limit]
        if "startTime" in received:
            start = int(received["startTime"])
            end = int(received.get("endTime", 2**63))
            return [dict(r) for r in rows if start <= r["time"] <= end][:limit]
        return [dict(r) for r in rows[-limit:]]

    def private_get_account_commission(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("private_get_account_commission", params)
        return json.loads(json.dumps(self._commission))
