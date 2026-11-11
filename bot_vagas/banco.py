"""Memória do bot: guarda num SQLite as vagas que já foram vistas/enviadas.

Assim o bot só manda no Telegram as vagas NOVAS de cada dia.
O sqlite3 vem com o Python: o banco inteiro é um único arquivo (dados/vagas.db).
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bot_vagas.gupy import Vaga

# Caminho padrão: dados/vagas.db na raiz do projeto (o GitHub Actions commita esse arquivo)
CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "vagas.db"

logger = logging.getLogger(__name__)

# "IF NOT EXISTS": rodar isto todo dia é seguro, só cria a tabela na primeira vez
CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS vagas_vistas (
    id       INTEGER PRIMARY KEY,  -- id da vaga na Gupy (o que importa para deduplicar)
    titulo   TEXT,
    empresa  TEXT,
    url      TEXT,
    vista_em TEXT NOT NULL         -- data/hora UTC em que a vaga entrou no banco
)
"""


def conectar(caminho: str | Path = CAMINHO_PADRAO) -> sqlite3.Connection:
    """Abre (ou cria) o banco e garante que a tabela existe."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)  # cria a pasta "dados" se faltar
    conn = sqlite3.connect(caminho)
    with conn:  # "with conn" confirma (commit) a transação no final
        conn.execute(CRIAR_TABELA)
    return conn


def esta_vazio(conn: sqlite3.Connection) -> bool:
    """True se nenhuma vaga foi registrada ainda (primeira execução do bot)."""
    return conn.execute("SELECT 1 FROM vagas_vistas LIMIT 1").fetchone() is None


def separar_novas(conn: sqlite3.Connection, vagas: list[Vaga]) -> list[Vaga]:
    """Devolve só as vagas que ainda NÃO estão no banco (mantendo a ordem)."""
    vistas = {linha[0] for linha in conn.execute("SELECT id FROM vagas_vistas")}
    return [v for v in vagas if v.id not in vistas]


def registrar(conn: sqlite3.Connection, vagas: list[Vaga]) -> int:
    """Grava as vagas no banco e devolve quantas foram gravadas de fato.

    Deve ser chamada só DEPOIS do envio no Telegram dar certo: se o envio
    falhar, as vagas continuam "novas" e são reenviadas na próxima execução.
    """
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    antes = conn.total_changes
    with conn:
        # "OR IGNORE": se o id já existe, pula sem dar erro
        conn.executemany(
            "INSERT OR IGNORE INTO vagas_vistas (id, titulo, empresa, url, vista_em) "
            "VALUES (?, ?, ?, ?, ?)",
            [(v.id, v.titulo, v.empresa, v.url, agora) for v in vagas],
        )
    gravadas = conn.total_changes - antes
    logger.info("Banco: %d vagas registradas (%d recebidas)", gravadas, len(vagas))
    return gravadas


def inicializar(conn: sqlite3.Connection, vagas: list[Vaga]) -> int:
    """Primeira execução: registra as vagas atuais sem enviar nada.

    Evita que o primeiro envio traga centenas de vagas "novas" de uma vez.
    """
    return registrar(conn, vagas)
