# CLAUDE.md — bot-vagas

Bot que roda 1x por dia (GitHub Actions), busca vagas de estágio em TI na Gupy, filtra por
palavras-chave e localização, guarda as vagas já vistas em SQLite e envia as novas numa única
mensagem no Telegram (HTML, link "Ver vaga").

O projeto é feito **em fases, uma por vez**. Antes de implementar cada fase, explicar o plano
em linguagem simples; depois, explicar as partes principais do código.

## Comandos
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip3 install -r requirements.txt
pytest -v                    # testes (nunca chamam a Gupy de verdade)
```

## Convenções
- Python **3.12**: sintaxe moderna (`str | None`, `list[str]`), `tomllib` da biblioteca padrão,
  sem `from __future__`.
- Comentários e mensagens em português do Brasil.
- Configuração (termos, palavras-chave, palavras excluídas, estados) fica em `config.toml`,
  nunca fixa no código.
- Segredos (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`) só via variáveis de ambiente: `.env` local
  (fora do Git) e GitHub Secrets no Actions. Manter `.env.example` atualizado.
- Testes com pytest + `responses` (simula a API). Toda funcionalidade nova ganha teste.
- Tudo gratuito; repositório público.
- Commits sem `Co-Authored-By` nem menção ao Claude. Fazer `git push` logo após cada commit.

## API da Gupy
- Endpoint: `https://portal.gupy.io/api/job-search/jobs` (o antigo
  `portal.api.gupy.io/api/v1/jobs` responde 404). Parâmetros: `jobName`, `limit`, `offset`.
- Resposta: `data` (lista de vagas) + `pagination` (`limit`, `offset`, `total`).
- Sempre usar o User-Agent próprio do bot (`USER_AGENT` em `gupy.py`); **nunca imitar navegador**.
- Paginação: `offset += len(pagina)` (não assumir que `limit` é respeitado); parar em página
  vazia, ao atingir `total` ou em `max_paginas`. Pausa entre requisições (`pausa_segundos`).
- Campos usados: `id`, `name`, `careerPageName`, `jobUrl`, `city`, `state`, `workplaceType`
  (`"on-site"`, `"hybrid"`, `"remote"`), `type`, `publishedDate`.
  - Não existe mais `isRemoteWork`: remota = `workplaceType == "remote"`.
  - `state` vem por extenso ("Rio de Janeiro") e às vezes `""` → tratar como ausente.
  - `type == "vacancy_type_internship"` marca estágio (`Vaga.eh_estagio`).
  - `type == "vacancy_type_talent_pool"` marca banco de talentos (`Vaga.eh_banco_talentos`).

## Estrutura
- `bot_vagas/config.py` — `carregar_config()`.
- `bot_vagas/gupy.py` — `Vaga` (dataclass), `buscar_vagas()` (um termo, paginado) e
  `buscar_todos()` → `(vagas, termos_com_falha)`. Deduplica por `id`; `Vaga.termos` guarda
  todos os termos que encontraram a vaga. Um termo com erro não interrompe os outros.
- `bot_vagas/filtros.py` — `normalizar()`, `contem_palavra()`, `passa_palavras()`,
  `passa_localizacao()` e `filtrar_vagas(vagas, config)`.
- `bot_vagas/banco.py` — `conectar()`, `esta_vazio()`, `separar_novas()`, `registrar()` e
  `inicializar()`. Tabela `vagas_vistas` (`id` da Gupy como chave).
- `dados/vagas.db` — banco SQLite **commitado** pelo Actions (exceção no `.gitignore`).

## Regras de filtro (Fase 2, implementadas)
- Normalizar textos antes de comparar (minúsculas, sem acento).
- Todas as palavras (chave e excluídas) comparadas como palavra inteira, aceitando plural
  com "s" ("intern" não casa "internacional"; "estagio" casa "estágios").
- Aceitar a vaga se `eh_estagio` **ou** se o título tiver uma palavra-chave; descartar se
  tiver palavra excluída.
- Localização: checar **remota primeiro** (aceita de qualquer lugar, pois pode vir com a
  cidade da sede); senão, exige estado em `estados_permitidos`; sem local informado passa
  com "Local não informado" (se `aceitar_local_nao_informado`).
- Banco de talentos: não tem o tipo estágio, então passa se o título tiver palavra-chave;
  fica marcado por `eh_banco_talentos`.

## Regras do banco (Fase 3, implementadas)
- Grava só as vagas **aceitas pelo filtro**; se o filtro mudar, vagas antes recusadas aparecem
  como novas (desejado).
- `registrar()` só **depois** do envio no Telegram dar certo; se o envio falhar, as vagas
  continuam novas e saem na próxima execução.
- `INSERT OR IGNORE`: registrar a mesma vaga duas vezes não dá erro.

## Regras combinadas para as próximas fases
- **Fase 4 — Telegram (`telegram.py`):** HTML com link "Ver vaga"; etiqueta "Banco de
  talentos" nas vagas com `eh_banco_talentos`; dividir mensagens acima de
  4096 caracteres; "Nenhuma vaga nova hoje" quando não houver vagas; aviso de falha em caso de
  erro; aviso de busca parcial quando houver `termos_com_falha`.
- **Fase 5 — `main.py`:** ordem: buscar → filtrar → `separar_novas` → enviar → `registrar`.
  - `--dry-run` mostra a mensagem no terminal sem enviar (e sem registrar no banco).
  - `--inicializar` só popula o banco (`inicializar()`), sem enviar mensagem.
  - Banco vazio sem `--inicializar`: inicializar automaticamente e enviar só um aviso no
    Telegram, tipo "Bot iniciado: N vagas registradas. A partir de amanhã você recebe só as
    novas."
- **Fase 6 — GitHub Actions:** execução diária, Secrets do Telegram, commit do `dados/vagas.db`.

## Status
- [x] Fase 1 — estrutura + busca na Gupy
- [x] Fase 2 — filtros (palavras-chave, localização, banco de talentos)
- [x] Fase 3 — banco SQLite de vagas já vistas
- [ ] Fases 4 a 6
