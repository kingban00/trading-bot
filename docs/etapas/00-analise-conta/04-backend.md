# Etapa 00 — Backend (`00-analise-conta`)

## Passo 0 — Bootstrap de infra

**Status: CONCLUÍDO.**
- O `dev-backend` criou os arquivos de infra, mas não conseguiu validá-los, porque o Git Bash do agente falhou no host com `fork: Resource temporarily unavailable` (`0xC0000142`).
- A validação foi feita pela sessão principal, via PowerShell, sem alterar nenhum arquivo (as evidências estão abaixo).

### Arquivos criados

- `docker-compose.yml`: só o serviço `bot`, com `build: ./backend`, `working_dir: /app`, bind mount `./backend:/app`, `env_file` com `path: .env` e `required: false`, e `command` padrão `python -m analysis.account_report`.
- `backend/Dockerfile`: imagem `python:3.12-slim`. A camada de dependências instala `.[test]` a partir só do `pyproject.toml`, depois copia o código. Usa o usuário não-root `bot` (uid 1000).
- `backend/.dockerignore`: exclui caches Python, `*.egg-info` e `.env*` do contexto de build.
- `backend/pyproject.toml`:
  - Dependências de runtime: `ccxt>=4.3` e `pydantic-settings>=2.2`.
  - Extra `test`: `pytest>=8.0` e `pytest-socket>=0.7`.
  - Configuração do pytest: `testpaths=["tests"]`, `pythonpath=["."]` e `addopts="--disable-socket --strict-markers"`.
- `.env.example`: `BINANCE_API_KEY=` e `BINANCE_API_SECRET=` vazios (chave somente leitura), mais placeholders comentados das fases futuras.

Não foram criados `backend/tests/`, `conftest.py` nem código de negócio.

### Decisões

1. **Layout plano com descoberta explícita.** `[tool.setuptools.packages.find] include = ["analysis*", "core*", "exchange*"]`. Isso evita o erro "Multiple top-level packages" quando os pacotes e `tests/` existirem lado a lado.
2. **Instalação em duas camadas.** As dependências ficam numa camada própria, então mudar o código não reinstala nada. Em desenvolvimento, o bind mount sobrepõe o código copiado.
3. **Dependências de teste na imagem do `bot`.** Assim `docker compose run --rm bot pytest` funciona direto.
4. **`--strict-markers`.** Pega markers digitados errado. Não afrouxa nada.
5. **`PYTHONDONTWRITEBYTECODE=1`.** Evita `__pycache__` no diretório montado.
6. **Sem volume nomeado.** Nesta fase não há cache persistente; a decisão será revista quando a A8 entrar.
7. **`env_file` com `required: false`.** Os testes rodam sem `.env` (CA-23/24).

### Saída real (validação, 2026-11-19)

```
> docker compose version
Docker Compose version v5.7.0

> docker compose run --rm bot pytest -VV        (sem .env presente)
 Image binance-bot Built
This is pytest version 9.2.0, imported from /usr/local/lib/python3.12/site-packages/pytest/__init__.py
registered third-party plugins:
  pytest-socket-0.8.1 at /usr/local/lib/python3.12/site-packages/pytest_socket/__init__.py
EXIT=0

> docker compose run --rm bot pytest
PytestConfigWarning: No files were found in testpaths; consider removing or adjusting your testpaths
configuration. Searching recursively from the current directory instead.
============================== 1 warning in 0.11s ==============================
EXIT=5   (no tests ran: esperado neste passo)

> docker compose run --rm bot sh -c "id && touch /app/.write_probe && ..."
uid=1000(bot) gid=1000(bot) groups=1000(bot)
GRAVA_OK
```

Versões instaladas: ccxt 4.5.93, pydantic-settings 2.16.3, pytest 9.2.0 e pytest-socket 0.8.1.

### Pendências do Passo 0 (todas resolvidas)

1. **Ambiente validado:** a imagem foi construída e o pytest roda sem `.env`. Sem testes, o código de saída é 5.
2. **Docker Compose:** a versão é v5.7.0, acima da 2.24, então o `required: false` funciona.
3. **Gravação no bind mount:** o usuário uid 1000 consegue gravar em `/app`, portanto o `.pytest_cache` funciona.
4. **`testpaths` inexistente:** o pytest só emite um aviso e busca a partir do diretório atual, sem erro. O aviso some quando o `autor-testes` criar `backend/tests/`.

### Observação do ambiente

O Bash (Git Bash) dos agentes está falhando no host com um erro de fork. Os agentes que dependem de Bash (`autor-testes`, `dev-backend` e `verificador`) podem precisar que a sessão principal execute os comandos Docker via PowerShell e lhes repasse as saídas.

## Implementação (etapa 4)

_A preencher depois do G3._
