# Etapa 00 — Análise da conta (`00-analise-conta`)

> Fonte: plano mestre `~/.claude/plans/voc-um-engenheiro-whimsical-globe.md` (Fase 0, "Execução de ordens", "Gestão de risco", "Segurança", "Metas e métricas", "Histórico de revisões") e `CLAUDE.md`.
> Raiz do repositório: `C:\dev\Binance`.

## Escopo

1. **Bootstrap mínimo de infraestrutura** (nota da Fase 0 no plano):
   - `docker-compose.yml` só com o serviço `bot` (imagem Python 3.12, build a partir de `backend/`, código montado e `env_file` para `.env`).
   - `backend/Dockerfile` (implícito no plano).
   - `backend/pyproject.toml` só com as dependências desta fase: `ccxt`, `pydantic-settings` e as de teste (`pytest` e um bloqueador de rede, como `pytest-socket`). As demais ficam para a Fase 1.
   - `.env.example` com `BINANCE_API_KEY=` e `BINANCE_API_SECRET=` vazios e um comentário dizendo que a chave da Fase 0 é **somente leitura**. As outras variáveis do plano entram como placeholders, sem nenhum consumo nesta fase.
2. **Portas (Protocols) de leitura**, pequenas e separadas por papel (princípio I do SOLID):
   - `ApiKeyPermissionReader`: restrições da chave, via `GET /sapi/v1/account/apiRestrictions`.
   - `BalanceReader`: saldos Spot com `free` e `locked`.
   - `MarketData`: preços atuais.
   - `TradeHistoryReader`: trades recentes por símbolo, via `myTrades`.
   - `FeeReader`: taxas maker/taker e desconto via BNB.
   - Nenhuma porta expõe criação ou cancelamento de ordem.
3. **Adaptador de borda** (ccxt) que implementa as portas, converte as respostas em tipos do domínio com `Decimal` e traduz os erros da exchange para exceções do domínio.
4. **Núcleo puro de análise** (sem I/O), em `backend/analysis/`:
   - Avaliação de cada ativo em USDT (total = `free` + `locked`).
   - Saldo operável.
   - Concentração por ativo.
   - Ativos parados, poeira e ativos sem cotação.
   - Resumo de trades recentes.
   - Taxas efetivas.
   - Capital sugerido (coerente com o "Capital alocado" da A6).
   - Perfil de risco sugerido, com os parâmetros exatos da tabela do plano.
5. **CLI** `python -m analysis.account_report`, com injeção de dependências. Fluxo, nesta ordem:
   1. Valida as credenciais.
   2. Verifica as permissões da chave.
   3. Coleta os dados.
   4. Analisa.
   5. Renderiza o relatório.
   - Códigos de saída distintos por tipo de falha.
6. **Decisão sobre rodar sem chave:**
   - O relatório **não** roda sem chave. Ele termina com uma mensagem clara, que cita as variáveis ausentes, com código ≠ 0 e **sem nenhuma chamada de rede**.
   - O relatório também **se recusa a rodar** se a chave tiver qualquer permissão além de leitura.
   - Justificativa:
     - O plano exige uma chave separada e somente leitura.
     - Não existe um modo útil sem chave.
     - Falhar cedo evita expor uma chave com poder de movimentar fundos.
     - A verificação é feita pela própria API (`apiRestrictions`).
   - Uma chave sem restrição de IP gera um aviso destacado (veja as Perguntas em aberto).
7. **Testes de backend** (pytest com fakes, sem rede e sem chave real), via `docker compose run --rm bot pytest`.

## Fora de escopo

- Qualquer envio, cancelamento ou consulta de ordens abertas. A Fase 0 não opera.
- Postgres, Alembic, modelos, `core/config.py` completo, `exchange/client.py` com os modos paper/testnet/live, `exchange/filters.py` e `indicators.py` (todos da Fase 1).
- Gravar o capital sugerido ou o perfil em `strategy_config`. O relatório só **sugere**.
- Estratégia, regime, sizing, guard, backtest e meta mensal sugerida (depende do backtest).
- Métricas de desempenho (CAGR, Sharpe etc.).
- Mercados que não sejam Spot, exceto identificar e excluir do saldo operável os tokens de Earn (`LD*`).
- Frontend (N/A) e E2E (N/A).

## Dependências

| Dependência | Origem | Situação |
|---|---|---|
| Governança (`CLAUDE.md` com fases 0–8, `relator`) | Plano | Concluída |
| `.gitignore` cobrindo `.env` e `reports/` | Segurança | Concluída |
| Projeto fora do OneDrive (`C:\dev\Binance`) | Segurança | Concluída |
| `docs/etapas/README.md` | Relatório de fim de fase | Criado pelo `relator` no fim da fase |
| Repositório git | A7 / `verificador` | Inexistente (veja a Pergunta 8) |
| Docker no host | Contexto | Disponível |
| Chave somente leitura no `.env` | Segurança | Do usuário; só para a execução manual, não para os testes |

## Riscos

1. **Vazamento de segredo:** as exceções do ccxt incluem a URL com `signature=`. Mitigação: traduzir as exceções com mensagem sanitizada.
2. **Chave com poder de trading ou saque:** checar `apiRestrictions` antes de qualquer outra leitura, com uma lista explícita de permissões proibidas.
3. **`float` do ccxt:** a conversão deve partir das strings brutas (`info`), e os testes devem garantir que só `Decimal` circula no domínio.
4. **Ativos sem par USDT:** pares inversos, ativos deslistados e tokens de Earn podem distorcer o total.
5. **`myTrades` exige um símbolo:** uma chamada por par pesa no rate limit, e o histórico pode ficar incompleto.
6. **Relógio do container fora de sincronia:** erro -1021. Precisa de ajuste da diferença de tempo e de uma mensagem acionável.
7. **`env_file: .env` obrigatório:** os testes precisam rodar sem `.env` (`required: false`).
8. **Regras de negócio não definidas no plano:** veja as Perguntas.
9. **Coerência com a A6:** o capital sugerido sai só do USDT livre, menos a reserva. Holdings manuais nunca entram.
10. **Baseline sem git:** o `verificador` não consegue rodar `git diff --name-only`, e arquivos *untracked* não aparecem no diff.
11. **Permissões do `.claude/settings.json`:** `docker compose build` e a execução do relatório vão pedir confirmação.
12. **Escopo de dependências:** não inflar o `pyproject.toml` com dependências de fases futuras.
13. **Somente leitura:** os Protocols da Fase 0 não podem ganhar métodos de escrita.

## Critérios de aceite

Todos os critérios são verificáveis com `docker compose run --rm bot pytest`, usando fakes das portas, sem rede, sem chave real e sem `.env`. Frontend: **N/A**. E2E: **N/A**.

**Credenciais e permissões**

- **CA-1 — Credenciais ausentes:** com a chave e/ou o segredo ausentes ou vazios, o `main` termina com o código de configuração (≠ 0), a mensagem cita cada variável ausente e nenhuma porta é chamada.
- **CA-2 — Permissão proibida:**
  - Qualquer permissão proibida faz o `main` terminar com o código de "permissão recusada" (≠ 0, distinto do CA-1).
  - Permissões cobertas (teste parametrizado): `enableSpotAndMarginTrading`, `enableWithdrawals`, `enableInternalTransfer`, `permitsUniversalTransfer`, `enableMargin`, `enableFutures`, `enableVanillaOptions`.
  - A mensagem nomeia a(s) permissão(ões) encontrada(s), e nenhuma outra leitura é feita.
- **CA-3 — Leitura desligada:** com `enableReading` falso, o `main` recusa com o código de "permissão recusada" e uma mensagem específica.
- **CA-4 — Ordem das chamadas:** a primeira chamada é a de `ApiKeyPermissionReader`. As demais só ocorrem depois de uma verificação aprovada.
- **CA-5 — Chave sem restrição de IP:** com `ipRestrict` falso e só leitura, o comportamento segue a decisão do G1 (Pergunta 5).

**Segredos e erros**

- **CA-6 — Nada de segredo na saída:** nos cenários de sucesso, recusa e erro, o stdout, o stderr e as exceções não contêm a chave, o segredo nem `signature=`. Os testes usam valores sentinela.
- **CA-7 — Erros da exchange traduzidos:**
  - Erros de autenticação, rate limit, timestamp (-1021) e rede viram exceções do domínio.
  - O `main` termina com o código de "erro da exchange" e uma mensagem acionável; um erro de timestamp sugere verificar o relógio.
  - Nenhum erro é engolido silenciosamente.

**Avaliação de saldos**

- **CA-8 — Valor em USDT:** a quantidade total é `free + locked`, e o valor é quantidade × preço de `<ATIVO>USDT`. O USDT vale 1. Só `Decimal`; o teste falha se aparecer `float`.
- **CA-9 — Ativos sem par direto:** um par inverso (ex.: `USDTBRL`) é avaliado por 1/preço. Um ativo sem nenhum par vira "sem cotação", fica fora do total e não gera exceção.
- **CA-10 — Tokens de Earn:** os `LD*` (ou de uma lista configurável) aparecem no relatório, mas ficam fora do saldo operável e do capital sugerido.
- **CA-11 — Poeira:** abaixo do limiar nomeado, o ativo é poeira e não entra em "parados" nem em concentração relevante.

**Métricas da carteira**

- **CA-12 — Saldo operável:** é só o USDT `free`.
- **CA-13 — Concentração:** os percentuais somam 100% do patrimônio cotado (com tolerância), em ordem decrescente, e os ativos acima do limiar são sinalizados.
- **CA-14 — Ativos parados:** com relógio injetado, é "parado" o ativo que não é poeira nem USDT e não tem trade na janela de N dias. O limite da janela é testado nos dois lados.

**Trades e taxas**

- **CA-15 — Resumo de trades:** quantidade, volume em USDT e taxas por ativo de comissão (convertidas para USDT), com paginação. Os trades fora da janela são ignorados.
- **CA-16 — Escopo das consultas:** o histórico é consultado só para os pares aprovados (Pergunta 11), com número de chamadas limitado e verificável.
- **CA-17 — Taxas efetivas:**
  - O relatório mostra maker/taker padrão e as taxas efetivas com o desconto BNB, em `Decimal`.
  - Sai um aviso se o desconto estiver ativo sem saldo de BNB, e uma recomendação se o desconto estiver inativo.

**Sugestões**

- **CA-18 — Capital sugerido:**
  - Segue a fórmula aprovada (Pergunta 1) e é ≤ saldo operável − reserva.
  - Nunca inclui holdings manuais nem ativos não operáveis.
  - Sai em USDT e em %, e nunca é negativo.
- **CA-19 — Capital insuficiente:** abaixo do mínimo nomeado (notional mínimo × máx. posições do perfil), sai o aviso "capital insuficiente para o perfil".
- **CA-20 — Perfil sugerido:** é determinístico pela regra aprovada (Pergunta 2), e os parâmetros são exatamente os da tabela do plano.

**Relatório, isolamento e infraestrutura**

- **CA-21 — Relatório determinístico:**
  - As mesmas entradas e o mesmo relógio geram uma saída idêntica.
  - Seções obrigatórias: permissões, saldos, saldo operável, concentração, parados/poeira/sem cotação, trades, taxas, capital sugerido e perfil sugerido.
- **CA-22 — Somente leitura por construção:** um teste estrutural confirma que não existem `create_order`, `cancel_order` e similares nas portas do relatório.
- **CA-23 — Sem rede nos testes:** sockets bloqueados (`pytest-socket`), e a suíte passa sem `.env`.
- **CA-24 — Infraestrutura mínima:**
  - `docker compose run --rm bot pytest` funciona num clone sem `.env`.
  - O compose define só o serviço `bot`.
  - O `pyproject.toml` não traz dependências de fases futuras.
  - O `.env.example` não tem valores reais.
- **CA-25 — Arredondamento:** quantização nomeada (2 casas para USDT e %, precisão do ativo para quantidades) com `ROUND_HALF_EVEN`, coberta por testes.

## Perguntas em aberto

1. **Fórmula do capital sugerido e reserva padrão.** Proposta: USDT livre × (1 − reserva), com reserva padrão de 20%. Teto em % do patrimônio total?
2. **Critério do perfil sugerido.** Proposta: Conservador como padrão para a primeira entrada em live; Moderado só se o capital comportar as posições; Agressivo nunca sugerido automaticamente.
3. **Janelas:** 90 dias para "trades recentes" e para "ativo parado", ajustável por argumento.
4. **Limiares:** poeira < 5 USDT; concentração > 25%.
5. **Chave sem restrição de IP:** só avisar ou recusar?
6. **Saída:** só stdout, ou também um arquivo em `reports/` e/ou JSON?
7. **Ativos sem par USDT:** rotear por BTC ou só marcar "sem cotação"? Proposta: não rotear nesta fase.
8. **Antecipar o `git init` para a Fase 0**, com um commit inicial só da governança (autorização explícita) e o `verificador` complementando com `git status --porcelain -uall`.
9. **Permissões do Claude Code:** liberar `docker compose build bot` e `git status` no `.claude/settings.json`? (Decisão do usuário.)
10. **Adaptador:** ccxt (recomendado) ou `httpx` com HMAC próprio?
11. **Escopo do resumo de trades:** só pares `*USDT` ou também pares cruzados e em BRL?

## Decisões do G1 (respostas às perguntas em aberto)

| # | Decisão |
|---|---|
| 1 | Capital sugerido = USDT livre × (1 − reserva), com **reserva padrão de 20%**. Sem teto adicional em % do patrimônio nesta fase. |
| 2 | Perfil sugerido: **Conservador** como padrão. **Moderado** só se o capital comportar o máximo de posições do perfil (notional mínimo × máx. posições). **Agressivo** nunca é sugerido automaticamente. |
| 3 | Janela de **90 dias** para "trades recentes" e "ativo parado" (constante nomeada, ajustável por argumento da CLI). |
| 4 | Poeira: **< 5 USDT**. Concentração sinalizada acima de **25%**. |
| 5 | Chave sem restrição de IP: **só aviso** destacado, sem bloquear (CA-5: código 0 e aviso no relatório). |
| 6 | Saída no **stdout** e também em **JSON** em `reports/` (já está no `.gitignore`). |
| 7 | Ativos sem par USDT (direto ou inverso) ficam marcados como **"sem cotação"**, sem roteamento por BTC. |
| 8 | **`git init` antecipado para a Fase 0**, com um commit inicial só da governança (`CLAUDE.md`, `.gitignore`, `.claude/`), autorizado pelo usuário. Nada de push. |
| 9 | Permissões do `.claude/settings.json`: **sem alteração**. Os comandos não liberados continuam pedindo confirmação manual. |
| 10 | Adaptador com **ccxt**, convertendo valores para `Decimal` a partir das strings brutas (Risco 3). |
| 11 | Resumo de trades **só dos pares `*USDT`**. |

## Aprovação G1

- Data: 2026-11-19
- Aprovado por: Yann (dono do projeto), via respostas na sessão
