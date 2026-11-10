"""Busca de vagas na API pública do portal da Gupy.

Este módulo só BUSCA e ORGANIZA as vagas. Filtrar, guardar e enviar
ficam em outros módulos (fases seguintes).
"""

import logging
import time
from dataclasses import dataclass, field

import requests

# Endpoint usado pelo próprio portal.gupy.io (o antigo portal.api.gupy.io/api/v1 dá 404)
URL_API = "https://portal.gupy.io/api/job-search/jobs"
# Valor do campo "type" que marca vaga de estágio
TIPO_ESTAGIO = "vacancy_type_internship"
USER_AGENT = "bot-vagas/1.0 (projeto de portfolio; busca diaria de estagios)"
TIMEOUT_SEGUNDOS = 15

# Tradução do campo "workplaceType" da API para o nosso vocabulário
MODELOS = {
    "remote": "remoto",
    "hybrid": "híbrido",
    "on-site": "presencial",
}

logger = logging.getLogger(__name__)


@dataclass
class Vaga:
    """Uma vaga no NOSSO formato, independente de como a API nomeia os campos."""

    id: int
    titulo: str
    empresa: str
    url: str
    cidade: str | None
    estado: str | None
    remota: bool
    modelo: str  # "remoto", "híbrido", "presencial" ou "não informado"
    publicada_em: str | None
    tipo: str | None  # ex.: "vacancy_type_internship" (estágio)
    # Termos de busca que encontraram esta vaga (útil para avaliar os termos depois)
    termos: list[str] = field(default_factory=list)

    @property
    def local_texto(self) -> str:
        """Texto amigável do local, usado na mensagem do Telegram."""
        # Remota vem primeiro: a cidade, nesse caso, costuma ser só a sede da empresa
        if self.remota:
            return "Remoto"
        partes = [p for p in (self.cidade, self.estado) if p]
        return " - ".join(partes) if partes else "Local não informado"

    @property
    def eh_estagio(self) -> bool:
        """True se a própria Gupy marcou a vaga como estágio (usado no filtro da fase 2)."""
        return self.tipo == TIPO_ESTAGIO


def _texto_ou_none(valor) -> str | None:
    """Converte string vazia/espaços em None, para padronizar 'sem informação'."""
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def _converter(item: dict, termo: str) -> Vaga:
    """Transforma um item do JSON da Gupy em um objeto Vaga."""
    tipo_local = item.get("workplaceType")
    remota = tipo_local == "remote"  # o campo isRemoteWork não existe mais na API
    modelo = "remoto" if remota else MODELOS.get(tipo_local, "não informado")

    return Vaga(
        id=item["id"],  # sem id não dá para deduplicar: aqui é melhor dar erro
        titulo=(item.get("name") or "").strip(),
        empresa=(item.get("careerPageName") or "").strip(),
        url=item.get("jobUrl") or "",
        cidade=_texto_ou_none(item.get("city")),
        estado=_texto_ou_none(item.get("state")),
        remota=remota,
        modelo=modelo,
        publicada_em=item.get("publishedDate"),
        tipo=_texto_ou_none(item.get("type")),
        termos=[termo],
    )


def buscar_vagas(
    termo: str,
    limite: int = 100,
    max_paginas: int = 3,
    pausa: float = 1.0,
    session: requests.Session | None = None,
) -> list[Vaga]:
    """Busca todas as vagas de UM termo, percorrendo as páginas da API.

    Erros de rede/HTTP são propagados (quem chama decide o que fazer).
    """
    http = session or requests.Session()
    vagas: list[Vaga] = []
    offset = 0

    for numero_pagina in range(1, max_paginas + 1):
        if numero_pagina > 1:
            time.sleep(pausa)  # pausa educada entre requisições

        resposta = http.get(
            URL_API,
            params={"jobName": termo, "limit": limite, "offset": offset},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()  # status 4xx/5xx viram exceção
        corpo = resposta.json()

        pagina = corpo.get("data")
        if not isinstance(pagina, list):
            raise ValueError(f"Resposta inesperada da Gupy para '{termo}': sem lista 'data'")

        logger.info("'%s' página %d (offset %d): %d vagas", termo, numero_pagina, offset, len(pagina))

        if not pagina:
            break  # acabaram as vagas

        vagas.extend(_converter(item, termo) for item in pagina)

        # Avança pelo que REALMENTE veio, não pelo limite pedido
        offset += len(pagina)

        total = (corpo.get("pagination") or {}).get("total")
        if isinstance(total, int) and offset >= total:
            break  # já pegamos tudo que a API diz existir
    else:
        # O "else" de um for roda quando o laço termina sem "break"
        logger.warning("'%s': parou no limite de %d páginas", termo, max_paginas)

    return vagas


def buscar_todos(
    termos: list[str],
    limite: int = 100,
    max_paginas: int = 3,
    pausa: float = 1.0,
    session: requests.Session | None = None,
) -> tuple[list[Vaga], list[str]]:
    """Busca vários termos, junta as vagas sem repetir e registra falhas.

    Devolve (vagas_unicas, termos_com_falha).
    """
    http = session or requests.Session()
    por_id: dict[int, Vaga] = {}  # dicionário id -> Vaga, para deduplicar
    termos_com_falha: list[str] = []

    for indice, termo in enumerate(termos):
        if indice > 0:
            time.sleep(pausa)

        try:
            vagas = buscar_vagas(termo, limite, max_paginas, pausa, session=http)
        except (requests.RequestException, ValueError) as erro:
            # Um termo com problema não derruba a busca inteira
            logger.error("Falha ao buscar '%s': %s", termo, erro)
            termos_com_falha.append(termo)
            continue

        for vaga in vagas:
            existente = por_id.get(vaga.id)
            if existente is None:
                por_id[vaga.id] = vaga
            elif termo not in existente.termos:
                existente.termos.append(termo)

    return list(por_id.values()), termos_com_falha
