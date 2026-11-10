"""Testes do módulo filtros.py (não fazem nenhuma requisição)."""

import pytest

from bot_vagas.config import carregar_config
from bot_vagas.filtros import (
    contem_palavra,
    filtrar_vagas,
    normalizar,
    passa_localizacao,
    passa_palavras,
)
from bot_vagas.gupy import TIPO_BANCO_TALENTOS, TIPO_ESTAGIO, Vaga

# Configuração de teste: igual à do config.toml, mas fixa aqui para o teste não
# quebrar se alguém mudar o arquivo
CFG_FILTRO = {
    "palavras_chave": ["estagio", "estagiario", "estagiaria", "intern", "internship"],
    "palavras_excluidas": ["senior", "pleno", "trainee", "jovem aprendiz"],
}
CFG_LOCAL = {
    "estados_permitidos": ["Rio de Janeiro", "RJ"],
    "aceitar_local_nao_informado": True,
}
CONFIG = {"filtro": CFG_FILTRO, "localizacao": CFG_LOCAL}


def criar_vaga(id_vaga=1, titulo="Estágio em TI", tipo=TIPO_ESTAGIO,
               estado="Rio de Janeiro", cidade="Rio de Janeiro", remota=False) -> Vaga:
    """Cria uma Vaga com valores padrão; cada teste muda só o que importa."""
    return Vaga(
        id=id_vaga,
        titulo=titulo,
        empresa="Empresa X",
        url=f"https://empresax.gupy.io/jobs/{id_vaga}",
        cidade=cidade,
        estado=estado,
        remota=remota,
        modelo="remoto" if remota else "presencial",
        publicada_em=None,
        tipo=tipo,
    )


# ---------- Normalização e comparação de palavras ----------

def test_normalizar_tira_acento_e_maiusculas():
    assert normalizar("ESTÁGIO em Computação") == "estagio em computacao"
    assert normalizar(None) == ""


@pytest.mark.parametrize("titulo, esperado", [
    ("IT Intern", True),
    ("Internship - Data", False),        # "internship" é outra palavra-chave
    ("Summer Interns", True),            # plural
    ("Analista Internacional", False),   # "intern" não é palavra inteira aqui
    ("Comércio Internacional", False),
])
def test_intern_como_palavra_inteira(titulo, esperado):
    assert contem_palavra(titulo, "intern") is esperado


def test_plural_e_parenteses():
    assert contem_palavra("Programa de Estágios 2027", "estagio")
    assert contem_palavra("Estagiário(a) de Dados", "estagiario")


def test_excluida_nao_casa_pedaco_de_palavra():
    assert not contem_palavra("Estágio - foco em senioridade", "senior")
    assert contem_palavra("Estágio e Jovem Aprendiz", "jovem aprendiz")


# ---------- Filtro de palavras ----------

def test_tipo_estagio_passa_mesmo_sem_palavra_no_titulo():
    assert passa_palavras(criar_vaga(titulo="Desenvolvedor(a) Java"), CFG_FILTRO)


def test_titulo_com_estagio_passa_mesmo_com_outro_tipo():
    vaga = criar_vaga(titulo="Estágio em Dados", tipo="vacancy_type_effective")
    assert passa_palavras(vaga, CFG_FILTRO)


def test_sem_tipo_estagio_e_sem_palavra_chave_cai():
    vaga = criar_vaga(titulo="Analista de Dados", tipo="vacancy_type_effective")
    assert not passa_palavras(vaga, CFG_FILTRO)


def test_palavra_excluida_derruba_mesmo_sendo_estagio():
    assert not passa_palavras(criar_vaga(titulo="Desenvolvedor Sênior"), CFG_FILTRO)
    assert not passa_palavras(criar_vaga(titulo="Estágio ou Trainee em TI"), CFG_FILTRO)


# ---------- Banco de talentos ----------

def test_banco_de_talentos_de_estagio_passa_e_fica_marcado():
    vaga = criar_vaga(titulo="Banco de Talentos - Estágio em TI", tipo=TIPO_BANCO_TALENTOS)
    assert passa_palavras(vaga, CFG_FILTRO)
    assert vaga.eh_banco_talentos is True
    assert vaga.eh_estagio is False


def test_banco_de_talentos_sem_estagio_cai():
    vaga = criar_vaga(titulo="Banco de Talentos - TI", tipo=TIPO_BANCO_TALENTOS)
    assert not passa_palavras(vaga, CFG_FILTRO)


def test_vaga_comum_nao_e_banco_de_talentos():
    assert criar_vaga().eh_banco_talentos is False


# ---------- Filtro de localização ----------

def test_remota_passa_mesmo_com_sede_em_outro_estado():
    vaga = criar_vaga(remota=True, cidade="São Paulo", estado="São Paulo")
    assert passa_localizacao(vaga, CFG_LOCAL)


@pytest.mark.parametrize("estado", ["Rio de Janeiro", "RJ", "rio de janeiro"])
def test_presencial_no_rj_passa(estado):
    assert passa_localizacao(criar_vaga(estado=estado), CFG_LOCAL)


def test_presencial_em_outro_estado_cai():
    assert not passa_localizacao(criar_vaga(cidade="São Paulo", estado="São Paulo"), CFG_LOCAL)


def test_sem_local_depende_da_configuracao():
    vaga = criar_vaga(cidade=None, estado=None)
    assert passa_localizacao(vaga, CFG_LOCAL)
    assert not passa_localizacao(vaga, {**CFG_LOCAL, "aceitar_local_nao_informado": False})


# ---------- Filtro completo ----------

def test_filtrar_vagas_lista_mista():
    vagas = [
        criar_vaga(1),                                                   # passa
        criar_vaga(2, estado="São Paulo"),                               # cai: local
        criar_vaga(3, titulo="Analista Pleno", tipo="vacancy_type_effective"),  # cai
        criar_vaga(4, remota=True, estado="Minas Gerais"),               # passa: remota
        criar_vaga(5, titulo="Banco de Talentos | Estágio",
                   tipo=TIPO_BANCO_TALENTOS),                            # passa
        criar_vaga(6, cidade=None, estado=None),                         # passa: sem local
    ]
    aceitas = filtrar_vagas(vagas, CONFIG)
    assert [v.id for v in aceitas] == [1, 4, 5, 6]


def test_filtrar_com_config_real():
    # Garante que o config.toml tem as seções e chaves que o filtro espera
    config = carregar_config()
    aceitas = filtrar_vagas([criar_vaga(1), criar_vaga(2, estado="Bahia")], config)
    assert [v.id for v in aceitas] == [1]


def test_internship_passa_pela_propria_palavra_chave():
    vaga = criar_vaga(titulo="Internship - Data", tipo="vacancy_type_effective")
    assert passa_palavras(vaga, CFG_FILTRO)
