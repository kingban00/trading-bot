# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projeto

Bot de trade para Binance **Spot** (Python 3.12) com dashboard Angular. O objetivo é crescimento estável do saldo com uma estratégia híbrida adaptativa por regime e gestão de risco configurável.

- Plano mestre: `~/.claude/plans/voc-um-engenheiro-whimsical-globe.md`. Ele define as fases 0–8 (0 conta · 1 infra · 2 estratégia/risco · 3 backtest · 4 stress test em crises · 5 bot · 6 API · 7 dashboard · 8 go-live) e o "Histórico de revisões" (A1–A10 e complementos).
- Modos de execução: `MODE=paper|testnet|live` no `.env`. O avanço é sempre paper → testnet → live com capital pequeno → capital final.
- Tudo roda em Docker. Não há Python instalado no host.

## Arquitetura

Serviços do `docker-compose.yml`:

- `db`: PostgreSQL 16.
- `bot`: motor de trading.
- `api`: FastAPI com REST, WebSocket e JWT.
- `dashboard`: build Angular servido por nginx em `localhost:4200`, com proxy de `/api` para a `api`.
- `dashboard-test`: Node, usado para testes e build do frontend.
- `e2e`: Playwright.

**O bot e a API nunca conversam diretamente.** O Postgres é o barramento:

- `strategy_config`: versionada. A API grava, e o bot faz polling a cada 10 s e aplica sem reiniciar (hot reload).
- `commands`: pausar, retomar, fechar tudo e pânico. A API grava, e o bot executa e marca como feito.
- `bot_heartbeat` e `equity_snapshots`: o bot grava, e a API repassa à dashboard via WebSocket.

Pontos que exigem ler vários arquivos para entender:

- `backend/strategy/` e `backend/risk/` são **o mesmo código** usado pelo `bot/` (live/paper) e pelo `backtest/engine.py`. Não crie ramificações "só para backtest" nesses módulos.
- O fluxo de um sinal é `strategy/regime.py` → `strategy/hybrid.py` → `trend.py` ou `mean_reversion.py`. Depois vem `risk/sizing.py` + `risk/guard.py`, e por fim `bot/position_manager.py` → `exchange/client.py`. Todo arredondamento de quantidade e preço passa por `exchange/filters.py`.
- `exchange/client.py` abstrai os modos `paper`, `testnet` e `live`. `exchange/paper.py` simula as execuções (taxa de 0,1% + slippage) com preços reais.
- `bot/reconciler.py` é a fonte da verdade depois de um restart: ele sincroniza o banco com os saldos e as ordens reais na inicialização e a cada 5 min.

### Invariantes (não quebrar)

- Toda posição aberta tem um stop real na exchange. Para fazer venda parcial ou sair no alvo, é preciso cancelar o stop antes, porque ele trava o saldo, e depois recriá-lo com a quantidade restante.
- O bot só mexe em ordens e posições que ele mesmo abriu, identificadas pelo prefixo do `newClientOrderId` (`bnbot-`). Holdings manuais nunca são tocados.
- A reserva intocável e os limites do perfil Personalizado são validados **no backend**, não só na dashboard.
- O drawdown e a perda diária são calculados sobre o capital alocado ao bot, sem contar a reserva nem os holdings manuais.
- As chaves da Binance ficam só no `.env`. A API e a dashboard nunca as expõem nem as editam.

## Comandos

Valem a partir da etapa 1, quando `docker-compose.yml`, `backend/` e `dashboard/` passam a existir.

```bash
docker compose up -d                                   # sobe tudo (MODE do .env)
docker compose run --rm bot alembic upgrade head       # migrações
docker compose run --rm bot pytest                     # testes de backend
docker compose run --rm bot pytest tests/test_sizing.py::test_nome   # um teste
docker compose run --rm bot python -m analysis.account_report        # fase 0
docker compose run --rm bot python -m backtest.engine --symbols BTC/USDT,ETH/USDT --from 2023-01-01
docker compose run --rm bot python -m backtest.stress --profile moderado   # fase 4: crises C1–C8 e S1–S4
docker compose run --rm dashboard-test npm test        # testes unitários Angular (headless)
docker compose run --rm dashboard-test npm run build   # build do frontend
docker compose run --rm e2e npx playwright test        # E2E
```

O backtest tem de ser determinístico: a mesma entrada gera o mesmo relatório.

## Qualidade de código: TDD, Clean Code e SOLID

### TDD (o fluxo de agentes segue o ciclo red → green → refactor)
- **Red:** o `autor-testes` escreve os testes antes de existir código (etapa 2) e prova que eles falham pelo motivo esperado.
- **Green:** o `dev-backend` e o `dev-frontend` escrevem o **mínimo** de código para os testes passarem. Funcionalidade sem teste que a exija fica fora da etapa.
- **Refactor:** com tudo verde, os devs refatoram (nomes, duplicação, extração de funções) e rodam a suíte de novo. O refactor não muda comportamento nem testes.
- Se surgir um comportamento sem teste, ou se for preciso um teste de unidade interna, o dev não escreve o teste. Ele registra a necessidade em `Pendências`, e o fluxo volta ao `autor-testes` com aprovação humana.

### SOLID aplicado a este projeto
- **S:** cada módulo tem uma única responsabilidade.
  - `regime.py` só classifica o regime, e `sizing.py` só calcula o tamanho da posição.
  - `guard.py` só decide se pode operar, e `position_manager` só executa.
  - Nenhum desses módulos acessa a exchange ou o banco diretamente.
- **O:** uma nova sub-estratégia ou um novo perfil de risco entra como uma classe nova que implementa a interface existente. `hybrid.py` e `profiles.py` não ganham `if/elif` por tipo.
- **L:** os modos `paper`, `testnet` e `live` são implementações intercambiáveis da mesma interface de exchange. O código cliente nunca testa qual é o modo.
- **I:** as interfaces são pequenas, por papel (ex.: `MarketData`, `OrderExecutor`, `BalanceReader`), em vez de um cliente "faz tudo".
- **D:** `strategy/`, `risk/` e `bot/` dependem de abstrações (`typing.Protocol` em Python, tokens/injeção do Angular no frontend) recebidas por construtor. O ccxt, o SQLAlchemy e o HTTP ficam só nas bordas (`exchange/`, `core/db.py`, `api/`, services do `core/` do Angular). Isso é o que permite testar sem rede e reutilizar o mesmo código no backtest.

### Clean Code
- Use nomes do domínio (`stop_price`, `risk_per_trade`, `regime`) em vez de `data`, `tmp` ou `x`. Números mágicos viram parâmetro da `StrategyConfig` ou uma constante nomeada.
- Funções pequenas, com um nível de abstração cada. O cálculo fica puro, sem I/O: indicadores, regime, sizing e guard recebem dados e devolvem decisões.
- Dinheiro e quantidades usam `Decimal` no backend; nunca `float` em preço, quantidade ou saldo enviados à exchange.
- Nada de `except` genérico silencioso. Os erros da exchange são traduzidos para exceções do domínio e registrados em `Event`.
- Use type hints completos no Python e `strict` no TypeScript. No Angular, os componentes ficam só com a apresentação, e a lógica fica nos services e signals.
- Sem código morto, sem comentário que repete o código e sem duplicação entre bot e backtest.

## Fluxo de execução dos agentes

Uma **etapa** é uma fase (0–8) do plano mestre. Os artefatos de cada etapa ficam em `docs/etapas/<NN>-<slug>/` (ex.: `docs/etapas/01-infra/`). Os agentes estão definidos em `.claude/agents/`.

A sessão principal só **orquestra**: chama os agentes em ordem, para em cada gate e não implementa nada por conta própria.

1. `analista`: analisa a etapa do plano e produz `01-analise.md`. → **G1**
   - **Passo 0 (bootstrap de infra), só quando a etapa precisa de infraestrutura de teste que ainda não existe:**
     - Antes do `autor-testes`, o `dev-backend` cria apenas a infra, sem código de negócio (ex.: `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `.env.example`, configuração do pytest).
     - Ele prova que o ambiente funciona com uma suíte vazia.
     - O registro vai na seção "Passo 0" do `04-backend.md`, e o `revisor` confere esse passo.
2. `autor-testes`: escreve os testes da etapa e produz `02-testes.md`. → **G2**
3. `planejador`: planeja a execução e produz `03-plano.md`. → **G3**
4. `dev-backend`: implementa o backend Python (bot e API) e produz `04-backend.md`.
5. `dev-frontend`: implementa o frontend Angular e produz `05-frontend.md`. Se a etapa não tem frontend, registra "N/A" com justificativa.
6. `revisor`: revisa o código e produz `06-revisao.md`. → **G4**
7. `verificador`: roda os testes e produz `07-verificacao.md`. → **G5**
8. `relator`: produz `08-relatorio.md`, o relatório de fim de fase escrito para o dono do projeto. Ele cobre o que foi feito, como e por quê, a arquitetura com diagramas, as regras de negócio com exemplos, as evidências, os riscos e como conferir. Também atualiza o índice em `docs/etapas/README.md`. → **G6**

**A próxima fase só começa depois que o `08-relatorio.md` da fase anterior for aprovado no G6.**

Para onde o fluxo volta em caso de problema:

- Falha na etapa 7, ou achado crítico/alto na etapa 6: volta à etapa 3 (`planejador`).
- Defeito no próprio teste: volta à etapa 2 (`autor-testes`), com aprovação humana.
- Depois de duas voltas completas sem sucesso, o fluxo para e pede intervenção humana.

## Regras de testes

- Somente o `autor-testes` altera testes: `backend/tests/`, `dashboard/**/*.spec.ts` e `e2e/`.
- Nenhum agente enfraquece, remove ou ignora testes (`skip`, `xfail`, `xit`, `fdescribe`, asserts afrouxados) para alcançar o aceite.
- Todo teste novo deve falhar pelo motivo esperado antes da implementação. O `02-testes.md` registra essa saída "vermelha".
- **Baseline:** o `02-testes.md` lista cada arquivo de teste com o seu sha256. O `verificador` recalcula os hashes e cruza com `git diff --name-only`, e qualquer divergência reprova a etapa.
- Toda mudança de teste após a etapa 2 exige aprovação humana e um novo baseline.

## Aprovação humana

| Gate | Quando | O que se aprova |
|---|---|---|
| G1 | depois do 01 | escopo e critérios de aceite |
| G2 | depois do 02 | matriz de testes e baseline |
| G3 | depois do 03 | plano de execução |
| G4 | depois do 06 | revisão de código |
| G5 | depois do 07 | resultado da verificação |
| G6 | depois do 08 | relatório de fim de fase, commit e encerramento (libera a próxima fase) |

A aprovação fica registrada no rodapé do artefato correspondente, com data e "aprovado por".

## Nunca

- Realizar `git add` ou `git commit` sem autorização.
- Fazer `git push` sem autorização.
- Gerar respostas que não sejam em português do Brasil.
- Alterar testes para alcançar o aceite.
- Alterar testes fora do `autor-testes`.
- Enfraquecer, remover ou ignorar testes.
- Declarar sucesso com teste falhando.

## Definição de pronto por etapa

- Testes de backend, frontend e E2E passam (os que existirem até a etapa).
- Revisão aprovada sem achados críticos ou altos.
- Nenhum teste alterado sem autorização (baseline íntegro).
- Artefatos de 01 a 08 completos.
- README e documentação atualizados.
- Aprovação humana registrada (G1–G6).

## Mapa dos agentes

| Ordem | Agente | Ferramentas | Artefato |
|---|---|---|---|
| 1 | `analista` | Read, Grep, Glob | `01-analise.md` |
| 2 | `autor-testes` | Read, Grep, Glob, Edit, Write, Bash (testes via Docker) | `02-testes.md` |
| 3 | `planejador` | Read, Grep, Glob | `03-plano.md` |
| 4 | `dev-backend` | Read, Grep, Glob, Edit, Write, Bash (`docker compose run --rm bot pytest`) | `04-backend.md` |
| 5 | `dev-frontend` | Read, Grep, Glob, Edit, Write, Bash (`docker compose run --rm dashboard-test npm test` / `npm run build`) | `05-frontend.md` |
| 6 | `revisor` | Read, Grep, Glob, Bash (`git diff`) | `06-revisao.md` |
| 7 | `verificador` | Read, Grep, Glob, Bash (testes via Docker, `git diff --name-only`, `sha256sum`) | `07-verificacao.md` |
| 8 | `relator` | Read, Grep, Glob | `08-relatorio.md` |

Agentes com Read, Grep e Glob apenas são somente leitura e entregam o conteúdo do artefato à sessão principal, que o grava em `docs/etapas/`. Os comandos Bash permitidos a cada agente estão descritos no próprio arquivo dele em `.claude/agents/`. O `.claude/settings.json` libera os comandos de teste via Docker, `git diff` e `sha256sum`, e bloqueia `git add`, `git commit` e `git push`.
