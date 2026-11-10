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

## Estrutura
- `bot_vagas/config.py` — `carregar_config()`.
- `bot_vagas/gupy.py` — `Vaga` (dataclass), `buscar_vagas()` (um termo, paginado) e
  `buscar_todos()` → `(vagas, termos_com_falha)`. Deduplica por `id`; `Vaga.termos` guarda
  todos os termos que encontraram a vaga. Um termo com erro não interrompe os outros.
- `dados/vagas.db` — banco SQLite **commitado** pelo Actions (exceção no `.gitignore`).

## Regras combinadas para as próximas fases
- **Fase 2 — filtros (`filtros.py`):**
  - Normalizar textos antes de comparar (minúsculas, sem acento).
  - "intern" e "internship" comparadas como palavra inteira (não casar "internacional").
  - Aceitar a vaga se `eh_estagio` **ou** se o título tiver uma palavra-chave; descartar se
    tiver palavra excluída.
  - Localização: checar **remota primeiro** (aceita de qualquer lugar, pois pode vir com a
    cidade da sede); senão, exige estado em `estados_permitidos`; sem local informado passa
    com "Local não informado" (se `aceitar_local_nao_informado`).
- **Fase 3 — banco (`banco.py`):** SQLite em `dados/vagas.db`. Flag `--inicializar` na primeira
  execução só popula o banco, sem enviar mensagem.
- **Fase 4 — Telegram (`telegram.py`):** HTML com link "Ver vaga"; dividir mensagens acima de
  4096 caracteres; "Nenhuma vaga nova hoje" quando não houver vagas; aviso de falha em caso de
  erro; aviso de busca parcial quando houver `termos_com_falha`.
- **Fase 5 — `main.py`:** `--dry-run` mostra a mensagem no terminal sem enviar.
- **Fase 6 — GitHub Actions:** execução diária, Secrets do Telegram, commit do `dados/vagas.db`.

## Status
- [x] Fase 1 — estrutura + busca na Gupy
- [ ] Fases 2 a 6
