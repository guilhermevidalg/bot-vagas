# bot-vagas

Bot que roda 1x por dia (GitHub Actions), busca vagas de **estágio em TI** na API pública
do portal da Gupy, filtra por palavras-chave e localização, guarda as vagas já vistas em
SQLite e envia as novas no Telegram.

> 🚧 Em construção, feito em fases.

## Status das fases
- [x] Fase 1 — estrutura do projeto e busca de vagas na Gupy (`bot_vagas/gupy.py`)
- [ ] Fase 2 — filtros (palavras-chave, palavras excluídas, localização)
- [ ] Fase 3 — banco SQLite (`dados/vagas.db`) e `--inicializar`
- [ ] Fase 4 — envio no Telegram (HTML, divisão em 4096 caracteres)
- [ ] Fase 5 — `main.py` com `--dry-run`
- [ ] Fase 6 — GitHub Actions

## Como rodar localmente
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
pytest -v
```

## Configuração
- `config.toml`: termos de busca, palavras-chave, palavras excluídas e estados permitidos.
- `.env` (copie de `.env.example`): `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`. Nunca vai para o Git.
