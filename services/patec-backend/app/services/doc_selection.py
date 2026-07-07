"""Seleção do documento de engenharia CORRENTE do caso.

Revisões de especificação criam novos `Documento` tipo "engenharia" (a mesma
requisição, versão mais nova). Para análise (R1), extração (W1) e chat usamos
APENAS a versão mais recente de cada arquivo — senão o texto é concatenado em
duplicata (N revisões = N× o documento), inchando os prompts, multiplicando os
chunks da análise e travando o passo de consolidação (reduce).
"""

from app.models.documento import Documento


def eng_docs_correntes(docs: list[Documento]) -> list[Documento]:
    """Docs de engenharia deduplicados por nome de arquivo (mantém o mais recente).

    Arquivos com nomes diferentes são mantidos (partes distintas da engenharia);
    o MESMO nome enviado várias vezes (revisão de spec) colapsa na última versão.
    Preserva a ordem cronológica de primeira aparição de cada nome.
    """
    eng = [d for d in docs if d.tipo == "engenharia"]
    ordenados = sorted(eng, key=lambda d: d.criado_em)
    por_nome: dict[str, Documento] = {}
    for d in ordenados:
        por_nome[d.nome_arquivo] = d  # o mais recente do mesmo nome vence
    return list(por_nome.values())
