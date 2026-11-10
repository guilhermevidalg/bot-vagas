"""Testes do módulo gupy.py.

A biblioteca `responses` intercepta as chamadas do `requests`: nenhuma
requisição chega à Gupy de verdade. Nós definimos o que a "API" responde.
"""

from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses
from responses import matchers

from bot_vagas.config import carregar_config
from bot_vagas.gupy import URL_API, USER_AGENT, _converter, buscar_todos, buscar_vagas


# ---------- Funções auxiliares para montar respostas falsas ----------

def item_api(id_vaga, nome="Estágio em TI", **extras):
    """Cria um item no formato que a Gupy devolve."""
    item = {
        "id": id_vaga,
        "name": nome,
        "careerPageName": "Empresa X",
        "jobUrl": f"https://empresax.gupy.io/jobs/{id_vaga}",
        "city": "Rio de Janeiro",
        "state": "Rio de Janeiro",
        "workplaceType": "on-site",  # "on-site", "hybrid" ou "remote"
        "type": "vacancy_type_internship",
        "publishedDate": "2026-11-01T10:00:00.000Z",
    }
    item.update(extras)
    return item


def registrar_pagina(termo, offset, itens, total=None, status=200):
    """Registra uma resposta falsa para um termo + offset específicos."""
    # Formato atual: "data" + "pagination" (limit, offset, total).
    # Sem total informado, usamos um valor alto para não interferir no teste.
    corpo = {
        "data": itens,
        "pagination": {"limit": 100, "offset": offset, "total": total if total is not None else 9999},
    }
    responses.add(
        responses.GET,
        URL_API,
        json=corpo,
        status=status,
        match=[matchers.query_param_matcher(
            {"jobName": termo, "limit": "100", "offset": str(offset)}
        )],
    )


def offsets_chamados():
    """Lista os offsets usados em cada chamada registrada pelo responses."""
    return [int(parse_qs(urlparse(c.request.url).query)["offset"][0]) for c in responses.calls]


# ---------- Conversão do JSON para Vaga ----------

def test_converter_vaga_remota_com_cidade_da_sede():
    item = item_api(1, city="São Paulo", state="São Paulo", workplaceType="remote")
    vaga = _converter(item, "estágio TI")

    assert vaga.remota is True
    assert vaga.modelo == "remoto"
    assert vaga.cidade == "São Paulo"        # guardamos a cidade original...
    assert vaga.local_texto == "Remoto"       # ...mas o texto exibido é "Remoto"
    assert vaga.termos == ["estágio TI"]


def test_converter_vaga_hibrida_no_rio():
    vaga = _converter(item_api(2, workplaceType="hybrid"), "t")
    assert vaga.remota is False
    assert vaga.modelo == "híbrido"
    assert vaga.local_texto == "Rio de Janeiro - Rio de Janeiro"


def test_converter_guarda_tipo_estagio():
    estagio = _converter(item_api(10), "t")
    efetivo = _converter(item_api(11, type="vacancy_type_effective"), "t")

    assert estagio.tipo == "vacancy_type_internship"
    assert estagio.eh_estagio is True
    assert efetivo.eh_estagio is False


def test_estado_vazio_vira_ausente():
    # A API às vezes manda state como string vazia
    vaga = _converter(item_api(12, state=""), "t")
    assert vaga.estado is None
    assert vaga.local_texto == "Rio de Janeiro"  # só a cidade


def test_converter_sem_local_informado():
    item = {"id": 3, "name": "Estágio Dados", "city": "", "state": None}
    vaga = _converter(item, "t")

    assert vaga.cidade is None
    assert vaga.estado is None
    assert vaga.modelo == "não informado"
    assert vaga.local_texto == "Local não informado"


# ---------- Paginação ----------

@responses.activate
def test_offset_avanca_pelo_que_realmente_veio():
    # Pedimos 100, mas a "API" devolve só 10 por página
    registrar_pagina("estágio", 0, [item_api(i) for i in range(10)])
    registrar_pagina("estágio", 10, [item_api(i) for i in range(10, 20)])
    registrar_pagina("estágio", 20, [])

    vagas = buscar_vagas("estágio", limite=100, max_paginas=5, pausa=0)

    assert len(vagas) == 20
    assert offsets_chamados() == [0, 10, 20]


@responses.activate
def test_para_no_max_paginas():
    registrar_pagina("estágio", 0, [item_api(1), item_api(2)])
    registrar_pagina("estágio", 2, [item_api(3), item_api(4)])

    vagas = buscar_vagas("estágio", max_paginas=2, pausa=0)

    assert len(vagas) == 4
    assert len(responses.calls) == 2  # não pediu uma 3ª página


@responses.activate
def test_para_ao_atingir_total():
    registrar_pagina("estágio", 0, [item_api(1), item_api(2)], total=3)
    registrar_pagina("estágio", 2, [item_api(3)], total=3)

    vagas = buscar_vagas("estágio", max_paginas=10, pausa=0)

    assert [v.id for v in vagas] == [1, 2, 3]
    assert len(responses.calls) == 2  # não precisou pedir página vazia


@responses.activate
def test_envia_user_agent():
    registrar_pagina("estágio", 0, [])
    buscar_vagas("estágio", pausa=0)
    assert responses.calls[0].request.headers["User-Agent"] == USER_AGENT


@responses.activate
def test_erro_http_levanta_excecao():
    registrar_pagina("estágio", 0, [], status=500)
    with pytest.raises(requests.HTTPError):
        buscar_vagas("estágio", pausa=0)


# ---------- Vários termos ----------

@responses.activate
def test_buscar_todos_deduplica_e_junta_termos():
    registrar_pagina("estágio TI", 0, [item_api(1), item_api(2)])
    registrar_pagina("estágio TI", 2, [])
    registrar_pagina("estágio dados", 0, [item_api(2), item_api(3)])
    registrar_pagina("estágio dados", 2, [])

    vagas, falhas = buscar_todos(["estágio TI", "estágio dados"], pausa=0)

    por_id = {v.id: v for v in vagas}
    assert sorted(por_id) == [1, 2, 3]
    assert por_id[2].termos == ["estágio TI", "estágio dados"]
    assert por_id[1].termos == ["estágio TI"]
    assert falhas == []


@responses.activate
def test_buscar_todos_continua_quando_um_termo_falha():
    registrar_pagina("estágio TI", 0, [], status=500)
    registrar_pagina("estágio dados", 0, [item_api(7)])
    registrar_pagina("estágio dados", 1, [])

    vagas, falhas = buscar_todos(["estágio TI", "estágio dados"], pausa=0)

    assert [v.id for v in vagas] == [7]
    assert falhas == ["estágio TI"]


# ---------- Configuração ----------

def test_config_real_tem_as_chaves_principais():
    config = carregar_config()
    assert len(config["busca"]["termos"]) > 0
    assert config["busca"]["limite_por_pagina"] == 100
    assert "estagio" in config["filtro"]["palavras_chave"]
    assert "RJ" in config["localizacao"]["estados_permitidos"]
