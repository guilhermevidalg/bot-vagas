"""Testes do módulo banco.py.

A fixture `tmp_path` do pytest cria uma pasta temporária para cada teste:
nunca mexemos no dados/vagas.db de verdade.
"""

from bot_vagas.banco import conectar, esta_vazio, inicializar, registrar, separar_novas
from bot_vagas.gupy import Vaga


def criar_vaga(id_vaga: int) -> Vaga:
    """Cria uma Vaga simples; para o banco só o id importa de verdade."""
    return Vaga(
        id=id_vaga,
        titulo=f"Estágio {id_vaga}",
        empresa="Empresa X",
        url=f"https://empresax.gupy.io/jobs/{id_vaga}",
        cidade="Rio de Janeiro",
        estado="Rio de Janeiro",
        remota=False,
        modelo="presencial",
        publicada_em=None,
        tipo="vacancy_type_internship",
    )


def test_conectar_cria_pasta_arquivo_e_tabela(tmp_path):
    caminho = tmp_path / "subpasta" / "vagas.db"
    conn = conectar(caminho)

    assert caminho.exists()
    assert esta_vazio(conn)


def test_conectar_duas_vezes_mantem_os_dados(tmp_path):
    caminho = tmp_path / "vagas.db"
    conn = conectar(caminho)
    registrar(conn, [criar_vaga(1)])
    conn.close()

    conn = conectar(caminho)  # reabrir não pode apagar nada nem dar erro
    assert not esta_vazio(conn)
    assert separar_novas(conn, [criar_vaga(1)]) == []


def test_tudo_e_novo_no_banco_vazio(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    vagas = [criar_vaga(1), criar_vaga(2)]
    assert separar_novas(conn, vagas) == vagas


def test_separar_novas_devolve_so_as_ineditas_na_ordem(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    registrar(conn, [criar_vaga(2)])

    novas = separar_novas(conn, [criar_vaga(3), criar_vaga(2), criar_vaga(1)])
    assert [v.id for v in novas] == [3, 1]


def test_registrar_ignora_repetidas(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    assert registrar(conn, [criar_vaga(1), criar_vaga(2)]) == 2
    assert registrar(conn, [criar_vaga(1), criar_vaga(2)]) == 0   # já estavam lá
    assert registrar(conn, [criar_vaga(2), criar_vaga(3)]) == 1   # só a 3 é nova


def test_registrar_lista_vazia(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    assert registrar(conn, []) == 0
    assert esta_vazio(conn)


def test_registrar_guarda_dados_da_vaga(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    registrar(conn, [criar_vaga(7)])

    linha = conn.execute("SELECT titulo, empresa, url, vista_em FROM vagas_vistas").fetchone()
    assert linha[:3] == ("Estágio 7", "Empresa X", "https://empresax.gupy.io/jobs/7")
    assert linha[3]  # data/hora preenchida


def test_inicializar_e_depois_nada_e_novo(tmp_path):
    conn = conectar(tmp_path / "vagas.db")
    vagas = [criar_vaga(i) for i in range(5)]

    assert inicializar(conn, vagas) == 5
    assert separar_novas(conn, vagas) == []                        # dia seguinte, mesmas vagas
    assert [v.id for v in separar_novas(conn, vagas + [criar_vaga(9)])] == [9]
