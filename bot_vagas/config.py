"""Leitura do arquivo de configuração (config.toml)."""

import tomllib
from pathlib import Path

# Caminho padrão: config.toml na raiz do projeto (uma pasta acima deste arquivo)
CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "config.toml"


def carregar_config(caminho: str | Path = CAMINHO_PADRAO) -> dict:
    """Lê o arquivo TOML e devolve um dicionário com as configurações."""
    # O tomllib exige que o arquivo seja aberto em modo binário ("rb")
    with open(caminho, "rb") as arquivo:
        return tomllib.load(arquivo)
