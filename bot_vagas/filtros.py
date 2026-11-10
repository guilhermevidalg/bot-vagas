"""Filtros que decidem quais vagas interessam.

Duas perguntas para cada vaga:
1. Palavras: é estágio e não tem palavra excluída no título?
2. Localização: é remota, ou fica num estado permitido (ou sem local informado)?

As listas de palavras e estados vêm do config.toml, nunca do código.
"""

import logging
import re
import unicodedata

from bot_vagas.gupy import Vaga

logger = logging.getLogger(__name__)


def normalizar(texto: str | None) -> str:
    """Deixa o texto em minúsculas e sem acento ("ESTÁGIO" -> "estagio")."""
    if not texto:
        return ""
    # NFKD separa a letra do acento ("á" vira "a" + "´"); depois descartamos os acentos
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.lower()


def contem_palavra(texto: str, palavra: str) -> bool:
    """True se `palavra` aparece INTEIRA no texto (aceitando plural com "s").

    Exemplos: "intern" casa "Intern" e "Interns", mas não "Internacional";
    "estagio" casa "Estágios".
    """
    # \b = fronteira de palavra; s? = um "s" opcional no final (plural)
    padrao = r"\b" + re.escape(normalizar(palavra)) + r"s?\b"
    return re.search(padrao, normalizar(texto)) is not None


def passa_palavras(vaga: Vaga, cfg_filtro: dict) -> bool:
    """Aceita estágio (pelo tipo da Gupy ou pelo título) sem palavra excluída."""
    titulo = vaga.titulo

    if any(contem_palavra(titulo, p) for p in cfg_filtro.get("palavras_excluidas", [])):
        return False

    # Banco de talentos não tem o tipo "estágio": passa se o título tiver palavra-chave
    if vaga.eh_estagio:
        return True
    return any(contem_palavra(titulo, p) for p in cfg_filtro.get("palavras_chave", []))


def passa_localizacao(vaga: Vaga, cfg_local: dict) -> bool:
    """Remota passa sempre; senão exige estado permitido (ou local não informado)."""
    # Remota primeiro: a cidade/estado, nesse caso, costuma ser só a sede da empresa
    if vaga.remota:
        return True

    if vaga.estado is None:
        return bool(cfg_local.get("aceitar_local_nao_informado", False))

    permitidos = {normalizar(e) for e in cfg_local.get("estados_permitidos", [])}
    return normalizar(vaga.estado) in permitidos


def filtrar_vagas(vagas: list[Vaga], config: dict) -> list[Vaga]:
    """Aplica os dois filtros e devolve só as vagas aceitas (mantendo a ordem)."""
    cfg_filtro = config.get("filtro", {})
    cfg_local = config.get("localizacao", {})

    aceitas = [
        v for v in vagas
        if passa_palavras(v, cfg_filtro) and passa_localizacao(v, cfg_local)
    ]
    logger.info("Filtro: %d de %d vagas aceitas", len(aceitas), len(vagas))
    return aceitas
