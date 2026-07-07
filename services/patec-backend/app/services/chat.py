import json
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, AsyncGenerator

import httpx

from app.core.config import settings
from app.models.documento import Documento
from app.models.documento_chunk import DocumentoChunk
from app.models.item_parecer import ItemParecer
from app.models.mensagem_chat import MensagemChat
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.services.doc_selection import eng_docs_correntes
from app.services.prompts.analise import get_chat_persona
from app.services.state_machine import (
    ANALISE,
    CICLO_FORNECEDOR,
    VERIFICACAO_FINAL,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.chat_memory import ChatMemoryHit


_CHAT_MODO_CONVERSA = """

## MODO CONVERSA

Voce agora esta em modo de conversa com o especialista responsavel pelo parecer tecnico.
O parecer tecnico ja foi gerado e esta disponivel como contexto na primeira mensagem.

### REGRAS DE CONVERSA
1. Mantenha o mesmo rigor tecnico e persona de engenheiro senior de instrumentacao e automacao
2. Responda em portugues, de forma profissional e tecnica
3. Quando o especialista questionar uma classificacao, cite EXCLUSIVAMENTE o trecho exato e a localizacao (documento, pagina, secao) nos documentos da engenharia que originou o requisito
4. Se o especialista solicitar alteracoes, discuta tecnicamente antes de concordar - voce pode concordar se o argumento tecnico for valido
5. Voce pode sugerir reclassificacoes se convencido pelo argumento tecnico do especialista
6. NUNCA invente informacoes que nao estejam nos documentos originais analisados. Se voce nao encontrar uma informacao especifica no texto dos documentos fornecidos, diga EXPLICITAMENTE que nao encontrou - NUNCA fabrique dados como TAGs, numeros de serie, especificacoes ou valores que nao estejam literalmente no texto dos documentos
7. Se questionado sobre algo fora do escopo dos documentos, informe claramente que a informacao nao consta nos documentos analisados. Quando citar qualquer dado (TAGs, valores, especificacoes), COPIE o texto exato do documento - nunca parafraseie ou reconstrua de memoria
8. Seja objetivo e direto nas respostas, mas sem perder profundidade tecnica
9. Se um requisito que voce classificou nao estiver explicitamente nos documentos da engenharia, RECONHECA IMEDIATAMENTE o erro: informe que o item nao tem base documental e proponha sua remocao ou reclassificacao como D (Informacao Ausente do Fornecedor nao se aplica - neste caso, o item deve ser REMOVIDO por nao ter origem na documentacao da engenharia)
10. NUNCA use boas praticas de engenharia, normas implicitas ou conhecimento proprio como fundamento para criar ou manter um item do parecer. O fundamento DEVE ser sempre o texto literal dos documentos da engenharia fornecidos.

### RESTRICAO ABSOLUTA - FIDELIDADE AOS DOCUMENTOS
Todo item classificado no parecer tecnico deve ter rastreabilidade direta e explicita aos documentos da engenharia fornecidos.
Se voce nao consegue apontar o trecho exato do documento que origina um requisito, o item NAO deve existir no parecer.
Boas praticas, normas implicitas e conhecimento tecnico proprio NUNCA justificam a existencia de um item - apenas os documentos da engenharia o fazem.

### FORMATO DE RESPOSTA
Responda sempre em texto livre e conciso (markdown: **negrito**, listas curtas).
NUNCA reproduza a lista de requisitos nem a tabela de itens do parecer como tabela
ou texto na resposta — essas tabelas vivem na interface (Tabela do caso / widgets),
nao no chat. Se o usuario quiser ve-las/edita-las, use a acao apropriada.
"""

# Acao da JULIA: reavaliar/refazer a analise completa (R1). Substitui o modo de
# despejar JSON no chat — a reanalise roda pelo pipeline normal, com barra de progresso.
_JULIA_ACAO_REANALISAR = """
### ACAO: REAVALIAR / REFAZER A ANALISE COMPLETA (R1)
Quando o usuario pedir para REAVALIAR ou REFAZER a analise do documento inteiro
("quero reavaliar os requisitos", "refaz a analise", "analisa o documento de novo",
"roda a analise outra vez", "reavaliar a MR/proposta"), voce NAO gera tabela nem
JSON: voce dispara a reanalise completa, que reclassifica todos os requisitos
aprovados contra a proposta do fornecedor e mostra o progresso na conversa.
1. Confirme em 1 frase, natural, que vai refazer a analise agora.
2. Termine a resposta com este bloco (sem parametros):
<acao>{"tipo": "reanalisar"}</acao>
PROIBIDO ABSOLUTO: nunca escreva/cole JSON do parecer no chat, nunca liste todos os
itens em JSON, nunca "gere uma nova tabela" em texto. A reanalise e feita pelo
sistema, nao por voce escrevendo o resultado. O bloco <acao> e invisivel — nunca o cite.
"""

_JULIA_ACAO_EXTRAIR = """
### ACAO: EXTRAIR OS REQUISITOS (passo atual: setup.extrair)
O documento da engenharia ja foi recebido. O proximo passo e VOCE le-lo e extrair a
lista de requisitos que sera verificada na proposta. NAO existe mais painel de
perfis — a escolha acontece AQUI, nesta conversa.

Pergunte ao usuario, de forma natural e curta, QUANTOS requisitos ele quer que voce
extraia para analisar — OU se prefere que VOCE escolha os mais relevantes (para uma
conversa mais enxuta). Quando ele responder com intencao clara, execute terminando a
resposta com:
<acao>{"tipo": "extrair_requisitos", "perfil": "<perfil>", "escopo": "<recorte ou omita>"}</acao>

CAMPO `escopo` (CRITICO): se o usuario delimitou QUALQUER trecho do documento — um
capitulo ("Capitulo 2"), uma tabela ("a tabela de equipamentos", "a Lista de Equipos"),
uma secao ("SCOPE OF SUPPLY") ou uma faixa de itens ("itens 1.1 a 5A.1") — voce DEVE
capturar isso textualmente em `escopo`, JUNTANDO tudo o que ele disse ao longo da
conversa (ex.: "Apenas o Capitulo 2 (SCOPE OF SUPPLY) — todos os itens da tabela de
equipamentos"). Esse escopo e o que faz a extracao respeitar o recorte e enumerar CADA
LINHA da tabela; sem ele a extracao pega o documento INTEIRO e consolida demais. Se o
usuario NAO delimitou nada, OMITA o campo `escopo`.

Como traduzir a resposta em <perfil>:
- Um numero N (ex.: "quero 12", "uns 20 itens", "10") -> "custom_N" (ex.: "custom_12").
- "todos", "a tabela inteira", "tudo", "completo na integra", "integral" -> "integral".
- "escolhe voce", "os melhores", "os mais relevantes", "tanto faz", "pode decidir",
  "como achar melhor" -> VOCE decide um numero adequado ao TAMANHO e a COMPLEXIDADE do
  documento (foque nos requisitos mais relevantes) e emita "custom_N" com esse numero.
  DIGA na resposta quantos vai extrair antes de comecar (ex.: "Vou extrair os 16
  requisitos mais relevantes e ja te mostro a lista para revisar.").

Regras: execute so com intencao clara; se for ambiguo, pergunte antes. Depois da
extracao o usuario revisa e aprova a lista. O bloco <acao> e invisivel para o
usuario — nunca o cite nem o descreva.
"""

_JULIA_ACAO_COMPLEMENTARES = """
### ACAO: DOCUMENTOS COMPLEMENTARES (passo atual: setup.docs_complementares)
O documento PRINCIPAL da engenharia ja foi recebido — ele e a base de TODO o
parecer tecnico. Agora, ANTES de extrair os requisitos, pergunte de forma natural
e curta se ha DOCUMENTOS COMPLEMENTARES: referencias e normas linkadas no documento
principal, que servem apenas como apoio ao entendimento (NAO sao a base da analise).

- Se o usuario disser que tem / vai anexar: peca para ele anexar pelo clipe da
  conversa e aguarde — NAO emita acao ainda.
- Quando ele disser que NAO tem, que ja terminou de anexar, ou que pode seguir
  ("nao tenho", "sem complementares", "so esse mesmo", "pode seguir", "prossegue",
  "ja anexei, pode ir"), confirme em 1 frase natural e termine a resposta com:
<acao>{"tipo": "confirmar_complementares"}</acao>

Isso libera a etapa seguinte: a EXTRACAO dos requisitos (a proposta do fornecedor so
vem depois da aprovacao da lista). O bloco <acao> e invisivel para o usuario — nunca
o cite nem o descreva.
"""


_JULIA_PERSONA_BASE = """
Voce e a JULIA, assistente de engenharia da plataforma PATEC. Voce conduz o
engenheiro pelo fluxo completo do parecer tecnico de forma amistosa, direta e
profissional, sempre em portugues. Responda saudacoes e conversas naturalmente,
como uma colega de equipe — nunca com respostas roboticas.

### O FLUXO DO PARECER (caso tecnico)
SETUP -> REQUISITOS -> ANALISE -> CICLO_FORNECEDOR -> VERIFICACAO_FINAL -> FECHADO
1. Setup: o engenheiro envia o DOCUMENTO DA ENGENHARIA (a proposta do fornecedor so vem mais tarde, nao agora).
2. Requisitos (W1): voce extrai do doc de engenharia a lista de requisitos CANDIDATOS e mostra ao engenheiro; ele revisa, edita e APROVA — so entao a lista vira a referencia oficial no banco. SO DEPOIS de aprovar a lista e que o engenheiro envia a proposta do fornecedor.
3. Analise (R1): com a proposta do fornecedor recebida, cada requisito aprovado e classificado A-E contra ela.
4. Ciclo com fornecedor: o fornecedor responde pendencias; o engenheiro decide item a item (Aceitar/Esclarecer/Rejeitar/Reprovar caso).
5. Verificacao final: a proposta final e conferida contra os acordos; o engenheiro valida.
6. Fechamento (W6): desfecho Aprovado / Com pendencia / Reprovado.

### REGRAS
1. Os gates do fluxo sao decisoes humanas, mas o usuario pode aciona-los
   CONVERSANDO com voce: quando houver uma acao de transicao disponivel (secao
   "ACOES DE TRANSICAO") e o usuario confirmar com clareza, VOCE executa —
   NUNCA mande o usuario clicar em botoes. Se a transicao pedida NAO estiver
   listada em "ACOES DE TRANSICAO" — em especial VOLTAR a uma fase anterior
   (ex.: "cancelar o ciclo e voltar para a analise") — NAO prometa nem finja
   executar. O fluxo so anda PARA FRENTE; nao ha volta do ciclo para a analise.
   Diga com franqueza que isso nao e possivel por aqui nesta fase e ofereca o
   caminho real: para corrigir a classificacao de UM item, corrija no LUGAR
   (status/justificativa do item, SEM trocar de fase); se o DOCUMENTO da
   engenharia mudou, use "revisar especificacao". Nunca invente uma capacidade.
2. Fidelidade documental absoluta: nunca invente dados que nao estejam nos documentos fornecidos. Se nao encontrar, diga explicitamente.
3. O estado atual do fluxo esta na secao "ESTADO DO FLUXO" do contexto — use-o para orientar o usuario sobre o que fazer agora ("o proximo passo e...").
4. Comandos que o usuario pode digitar no chat: "ver tabela" (tabela do caso,
   direto do banco), "ver itens", "ver item N", "status", "exportar
   pdf/xlsx/docx", "carta", "revisar especificacao", "reanalisar", "fechar caso".
   A caixa de conversa tambem tem um clipe para anexar arquivos.
5. Quando voce aplicar uma mudanca (ex: na lista de requisitos), convide o
   usuario a conferir na "Tabela do caso" (botao no topo ou comando "ver tabela").
6. Quando o usuario perguntar como carregar, enviar, subir ou anexar documentos,
   explique que ele pode usar o clipe na caixa de conversa ou a area de upload
   visivel no passo atual. NUNCA peca para colar o texto do documento no chat
   como caminho principal de upload.
"""

_JULIA_ACAO_REQUISITOS = """
### ACAO: EDITAR A LISTA DE REQUISITOS EM REVISAO
O contexto contem um RASCUNHO DE REQUISITOS aguardando aprovacao (W1). Quando o
usuario pedir mudancas nessa lista (adicionar, remover, reescrever, mudar
prioridade, mesclar itens, RECORTAR POR SECAO etc.), voce DEVE aplica-las assim:
1. Explique em 1-3 frases o que voce mudou (sem mencionar blocos tecnicos).
2. Termine a resposta com o bloco abaixo, contendo a lista COMPLETA ja atualizada
   (todos os itens que PERMANECEM, renumerados 1..N, nao apenas os alterados),
   no mesmo schema do rascunho:
<acao>{"tipo": "atualizar_requisitos", "requisitos": [{"numero": 1, "categoria": "...", "descricao_requisito": "...", "referencia_engenharia": "...", "valor_requerido": "...", "prioridade": "ALTA|MEDIA|BAIXA", "norma_referencia": null}, ...]}</acao>
3. Novos itens so podem nascer de conteudo presente nos documentos da engenharia.
4. Se o pedido for ambiguo, pergunte antes de alterar.
5. NUNCA exiba JSON, listas de campos ou estruturas tecnicas no texto visivel da
   resposta — o JSON vai EXCLUSIVAMENTE dentro do bloco <acao>.
6. NUNCA termine prometendo mostrar a lista ("aqui esta a lista...") — a lista
   NAO aparece no texto. Diga que atualizou e aponte para a Tabela do caso.

### RECORTE POR SECAO / CAPITULO / INTERVALO (pedido comum — siga a risca)
Quando o usuario pedir para MANTER apenas um trecho do documento (ex: "deixe so os
itens do capitulo 8", "remova tudo que nao for da Lista de Equipos", "mantenha so
ate o item 5A.1", "tira as secoes 1 a 7"):
- Use o campo `referencia_engenharia` de cada requisito como ANCORA para decidir o
  que pertence ao trecho pedido. Tambem cruze com o TEXTO COMPLETO DA ENGENHARIA no
  contexto para confirmar a fronteira (onde o capitulo/secao comeca e termina).
- Mantenha EXATAMENTE os requisitos do trecho pedido (incluindo os limites citados)
  e remova todo o resto. Inclua tambem os itens daquele trecho que por acaso nao
  estejam no rascunho atual, se forem requisitos verificaveis.
- NAO invente, NAO mescle e NAO divida requisitos para "encaixar" no recorte:
  apenas inclua/exclua. Um valor/parametro de um item (carga total, TAG, Wh/dia)
  pertence ao requisito daquele item (vai em valor_requerido), nunca vira item separado.
- Se algum requisito nao tiver `referencia_engenharia` clara e o texto nao permitir
  decidir com seguranca, pergunte em vez de adivinhar.
O bloco <acao> e invisivel para o usuario — nunca o cite nem o descreva.
"""

_JULIA_ACAO_REVISAO_SPEC = """
### ACAO: REVISAO DA ESPECIFICACAO (subir uma nova revisao do documento da engenharia)
A analise ja foi feita, mas a engenharia pode emitir uma NOVA REVISAO do
documento de requisicao/especificacao a qualquer momento — e comum e fundamental.

IMPORTANTE: a plataforma PATEC TEM upload de arquivos. Voce NAO e um "assistente
so de texto". Quando o engenheiro quiser trazer uma nova revisao, ele ANEXA o
ARQUIVO (PDF/DOCX/XLSX) aqui na conversa — NUNCA cola o texto. Por isso:
- NUNCA peca para "colar o conteudo/texto do documento".
- NUNCA diga que "nao consegue subir arquivos" ou que e "so um assistente de texto".
- NUNCA mande procurar botao, menu ou outra tela.

GATILHOS (assim que o usuario disser QUALQUER coisa nesse sentido, JA execute a acao):
- "o documento/especificacao/requisicao da engenharia mudou / foi atualizado / tem nova revisao/versao"
- "quero revisar a especificacao / atualizar o documento / trocar a base da analise"
- "quero subir / carregar / enviar / anexar o (novo) documento", "fazer upload"
- "tive uma alteracao no documento", "recebi uma nova revisao"

O QUE FAZER (ja na PRIMEIRA mensagem com esse sentido, sem enrolar):
1. Confirme em 1 frase, natural, que voce JA abriu o envio da nova revisao aqui na
   conversa. Ex: "Claro! Abri o envio aqui embaixo — e so anexar o arquivo da nova revisao."
2. Termine a resposta com este bloco (sem parametros — o engenheiro anexa o arquivo):
<acao>{"tipo": "revisar_especificacao"}</acao>

NAO espere o usuario "avisar quando estiver pronto" nem pergunte o nome do arquivo:
abra o upload de imediato. Eu comparo a nova revisao contra os requisitos do caso
e mostro o que mudou (itens alterados voltam ao fornecedor, removidos sao
desativados, novos entram) ANTES de aplicar qualquer coisa — nada e alterado sem a
confirmacao do engenheiro. O bloco <acao> e invisivel — nunca o cite nem o descreva.
"""


# Deteccao deterministica (sem LLM) da intencao de subir/revisar o documento da
# engenharia — rede de seguranca para quando a LLM esquece de emitir a acao e
# responde "cole o texto" em vez de abrir o upload (ver _JULIA_ACAO_REVISAO_SPEC).
_REVISAO_FRASES = (
    "nova revis", "nova vers", "outra revis", "outra vers",
    "revisar a espec", "revisar especific", "revisar o documento",
    "revisar o doc", "revisar aqui", "documento mudou", "mudou o documento",
    "mudanca no documento", "alteracao no documento", "alterei o documento",
    "documento foi atualizado", "atualizar o documento", "atualizar a espec",
    "trocar o documento", "trocar a espec", "substituir o documento",
    "novo documento da engenharia", "documento da engenharia mudou",
    "recebi uma nova", "saiu uma nova",
)
_REVISAO_VERBOS = (
    "subir", "carregar", "upload", "anexar", "enviar", "mandar", "adicionar",
)
_REVISAO_NOUNS = (
    "documento", "arquivo", "especificac", "requisic", "revis", "versao",
    "spec", "datasheet", "folha de dados",
)
_REVISAO_EXCLUI = ("fornecedor", "proposta", "resposta")


def _normalizar_texto(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# Tokens de negacao (ja normalizados, sem acento). Usados para NAO disparar os
# detectores deterministicos em frases negadas ("nao quero cancelar o ciclo",
# "nao precisa revisar a espec") — senao a JULIA declinava/abria upload contra a
# vontade do usuario (ver C1 da auditoria).
_NEGACOES = frozenset({"nao", "nunca", "jamais", "sem", "nem", "nenhum", "nenhuma"})


def _negacao_antes(texto_norm: str, alvo: str, janela: int = 4) -> bool:
    """True se houver um token de negacao nas ~`janela` palavras que antecedem a
    primeira ocorrencia de `alvo` no texto normalizado."""
    idx = texto_norm.find(alvo)
    if idx == -1:
        return False
    antes = texto_norm[:idx].split()[-janela:]
    return any(tok in _NEGACOES for tok in antes)


def detectar_intencao_revisao_spec(mensagem: str) -> bool:
    """True se o usuario claramente quer subir/revisar o documento da engenharia.

    Conservador de proposito: ou bate uma frase explicita, ou combina um verbo de
    upload com um substantivo de documento — sem confundir com o envio de uma
    resposta/proposta do fornecedor.
    """
    t = _normalizar_texto(mensagem)
    for frase in _REVISAO_FRASES:
        if frase in t and not _negacao_antes(t, frase):
            return True
    tem_verbo = any(v in t for v in _REVISAO_VERBOS)
    tem_noun = any(n in t for n in _REVISAO_NOUNS)
    if tem_verbo and tem_noun:
        # negacao antes do verbo OU do substantivo ("nao precisa subir o documento")
        gatilhos = [g for g in (*_REVISAO_VERBOS, *_REVISAO_NOUNS) if g in t]
        if any(_negacao_antes(t, g) for g in gatilhos):
            return False
        # nao disparar quando o assunto e a resposta/proposta do fornecedor
        if any(x in t for x in _REVISAO_EXCLUI) and not (
            "engenharia" in t or "especificac" in t or "revis" in t
        ):
            return False
        return True
    return False


# Deteccao deterministica (sem LLM) da intencao de VOLTAR a uma fase anterior /
# cancelar o ciclo — transicao que o fluxo NAO suporta (o caso so anda para frente;
# a unica regressao e a revisao de spec). Usada para a JULIA declinar com honestidade
# ANTES de chamar o LLM, em vez de prometer e falhar silenciosamente.
_VOLTAR_FRASES = (
    "voltar para a analise", "voltar pra analise", "voltar a analise",
    "voltar para analise", "voltar para a fase", "voltar de fase",
    "voltar para a etapa", "voltar a etapa", "fase anterior", "etapa anterior",
    "passo anterior", "cancelar o ciclo", "cancela o ciclo", "cancelar ciclo",
    "desfazer o ciclo", "sair do ciclo", "voltar atras", "reverter o caso",
    "reverter a fase", "reverter para",
)
_VOLTAR_VERBOS = (
    "voltar", "retornar", "reverter", "regredir", "desfazer", "cancelar", "anular",
)
_VOLTAR_ALVOS = (
    "analise", "fase anterior", "etapa anterior", "passo anterior", "o ciclo",
    "do ciclo", "ciclo do fornecedor", "ciclo com o fornecedor",
)


def detectar_intencao_voltar_fase(mensagem: str) -> bool:
    """True se o usuario quer VOLTAR a uma fase anterior / cancelar o ciclo.

    Conservador: bate uma frase explicita, ou combina um verbo de reversao com um
    alvo de fase/ciclo. Nao confunde com 'reanalisar' (refazer sem trocar de fase)
    nem com pedir para 'ver' a analise.
    """
    t = _normalizar_texto(mensagem)
    for frase in _VOLTAR_FRASES:
        if frase in t and not _negacao_antes(t, frase):
            return True
    tem_verbo = any(v in t for v in _VOLTAR_VERBOS)
    tem_alvo = any(a in t for a in _VOLTAR_ALVOS)
    if tem_verbo and tem_alvo:
        # negacao antes do verbo OU do alvo ("nao precisa voltar para a analise")
        gatilhos = [g for g in (*_VOLTAR_VERBOS, *_VOLTAR_ALVOS) if g in t]
        if any(_negacao_antes(t, g) for g in gatilhos):
            return False
        return True
    return False


# Deteccao deterministica (sem LLM) da escolha de quantos requisitos extrair, no
# passo setup.extrair — rede de seguranca para quando a LLM esquece o bloco <acao>
# (ja vimos o modelo ignorar instrucoes de prompt). Retorna o perfil ou None.
# "todos/tudo" so contam com limite de palavra e fora de saudacao ("tudo bem").
_EXTRACAO_TODOS_RE = re.compile(
    r"\b(todos|todas|integral|tabela inteira|tabela toda|lista inteira|"
    r"lista completa|sem limite|na integra|tudo que|extrai tudo|pega tudo|"
    r"quero tudo|analisa tudo|tudo de uma vez)\b"
)
_EXTRACAO_VOCE_ESCOLHE = (
    "escolhe voce", "escolha voce", "voce escolhe", "voce decide", "pode decidir",
    "os melhores", "mais relevantes", "tanto faz", "como achar melhor",
    "fica a seu criterio", "voce que sabe", "pode escolher", "fica a seu",
    "do seu jeito", "o que achar melhor",
)


def detectar_intencao_extracao(mensagem: str) -> str | None:
    """Mapeia a resposta do usuario (no passo setup.extrair) para um perfil de
    extracao: 'integral' | 'custom_N' | 'padrao' | None. Conservador: numero
    explicito vira custom_N; 'todos' vira integral; 'voce escolhe' cai no padrao
    (fallback — o ideal e a LLM decidir um numero pelo documento)."""
    t = _normalizar_texto(mensagem)
    if _EXTRACAO_TODOS_RE.search(t):
        return "integral"
    m = re.search(r"\b(\d{1,3})\b", t)
    if m:
        n = max(1, min(int(m.group(1)), 100))
        return f"custom_{n}"
    if any(f in t for f in _EXTRACAO_VOCE_ESCOLHE):
        return "padrao"
    return None


# Deteccao deterministica (sem LLM) de "nao tenho complementares / pode seguir", no
# passo setup.docs_complementares — rede de seguranca para liberar a etapa seguinte
# mesmo se a LLM esquecer o bloco <acao>.
_SEM_COMPLEMENTARES_FRASES = (
    "nao tenho", "nao ha", "nao possuo", "sem complementar", "nenhum complementar",
    "so esse", "so esse mesmo", "somente esse", "apenas esse", "so o principal",
    "pode seguir", "pode prosseguir", "prossegue", "prossiga", "pode ir",
    "pode continuar", "ja anexei", "terminei de anexar", "ja enviei tudo",
    "sem mais documentos", "nao tem complementar", "nada complementar",
    "nenhum outro", "nao, pode", "nao tem mais",
)


def detectar_sem_complementares(mensagem: str) -> bool:
    """True se o usuario indicou que nao tem complementares ou que pode seguir
    para a proxima etapa (no passo setup.docs_complementares)."""
    t = _normalizar_texto(mensagem)
    return any(f in t for f in _SEM_COMPLEMENTARES_FRASES)

_JULIA_ACAO_ITENS = """
### ACAO: CORRIGIR ITENS DO PARECER
O engenheiro pode pedir correcoes nos itens do parecer (individualmente no chat
ou em lote pelos comentarios da Tabela do caso). Quando o pedido for claro e
tecnicamente fundamentado, VOCE aplica as correcoes assim:
1. Explique brevemente o que vai mudar em cada item (sem JSON no texto).
2. Termine a resposta com o bloco de patch — APENAS os itens alterados e APENAS
   os campos alterados:
<acao>{"tipo": "atualizar_itens", "itens": [{"numero": 4, "status": "B", "justificativa_tecnica": "...", "acao_requerida": "..."}]}</acao>
3. Campos permitidos por item: status (A|B|C|D|E), justificativa_tecnica,
   acao_requerida, prioridade (ALTA|MEDIA|BAIXA), valor_requerido,
   valor_fornecedor, norma_referencia, descricao_requisito.
4. Se discordar tecnicamente de um comentario, discuta e NAO aplique aquele item
   — mas aplique os demais que forem procedentes. A palavra final e do engenheiro:
   se ele insistir, aplique.
5. Apos aplicar, aponte a Tabela do caso para conferencia.
O bloco <acao> e invisivel — nunca o cite nem o descreva.
"""

_JULIA_ACAO_EDITAR_REQUISITOS = """
### ACAO: EDITAR A LISTA DE REQUISITOS (ESCOPO) ANTES DE REAVALIAR
A analise ja rodou, mas o caso ainda esta na fase ANALISE (sem ciclo iniciado),
entao o engenheiro AINDA pode mexer em QUAIS requisitos da MR serao avaliados —
adicionar, remover, reescrever, mudar o recorte. Quando ele pedir para EDITAR/
REVER/ALTERAR A LISTA DE REQUISITOS (ex: "quero alterar os itens da MR que vamos
avaliar", "me da a tabela de requisitos sem a comparacao para eu avaliar",
"editar/ajustar a lista de requisitos", "rever quais requisitos entram"), voce:
1. Confirme em 1 frase, natural, que vai abrir a lista de requisitos para edicao.
2. Termine a resposta com este bloco (sem parametros):
<acao>{"tipo": "reabrir_requisitos"}</acao>
Isso reabre a TABELA EDITAVEL de requisitos (so os requisitos, SEM a comparacao
do fornecedor); ao aprovar a nova lista, a analise e refeita automaticamente.

NAO CONFUNDA:
- "editar a LISTA de requisitos / o escopo / quais itens avaliar" -> reabrir_requisitos (acima)
- "corrigir a classificacao de UM item ja analisado (status/justificativa)" -> atualizar_itens
- "refazer a analise SEM mudar a lista" -> reanalisar

PROIBIDO ABSOLUTO: NUNCA escreva/cole a lista de requisitos (nem dos itens) como
TABELA ou texto na resposta. A tabela aparece na interface, nao no chat. Diga que
abriu a edicao e pare. O bloco <acao> e invisivel — nunca o cite nem o descreva.
"""

# Acoes de transicao de fase disponiveis por passo ativo do fluxo
TRANSICOES_POR_STEP: dict[str, list[tuple[str, str]]] = {
    "requisitos.aprovar": [
        (
            "aprovar_requisitos",
            "aprova a lista de requisitos em revisao (W1); a analise comeca em seguida",
        ),
    ],
    "analise.resultado": [
        ("iniciar_ciclo", "inicia o ciclo com o fornecedor (W2)"),
    ],
}


def _julia_acoes_transicao(step_id: str) -> str:
    transicoes = TRANSICOES_POR_STEP.get(step_id, [])
    if not transicoes:
        return """
### ACOES DE TRANSICAO DE FASE (disponiveis agora)
NENHUMA neste passo. Se o usuario pedir para AVANCAR ou VOLTAR de fase (ex.:
"cancelar o ciclo e voltar para a analise"), NAO prometa nem finja executar:
explique com franqueza que isso nao e possivel por aqui agora e ofereca o
caminho real — corrigir a classificacao do item no LUGAR (sem trocar de fase),
ou "revisar especificacao" se o documento da engenharia mudou.
"""
    linhas = "\n".join(
        f'- <acao>{{"tipo": "{tipo}"}}</acao> — {descricao}'
        for tipo, descricao in transicoes
    )
    return f"""
### ACOES DE TRANSICAO DE FASE (disponiveis agora)
O usuario avanca o fluxo CONVERSANDO com voce — nunca mande clicar em botoes.
Quando ele confirmar com intencao clara (ex: "pode seguir", "aprova",
"esta bom, avanca", "perfeito, segue"), execute terminando a resposta com o
bloco da acao correspondente:
{linhas}
Regras: execute apenas com confirmacao clara do usuario; se houver ambiguidade,
pergunte. Nao execute duas vezes a mesma transicao. Ao executar, diga
naturalmente o que esta acontecendo (ex: "Aprovado! Ja estou iniciando a
analise...").
"""

# IMPORTANTE: as chaves devem cobrir TODOS os step-ids emitidos por
# frontend/src/components/julia/derive-step.ts — senao a JULIA recebe "n/a" no
# passo ativo (ver C5). O teste tests/unit/test_chat_detectors.py trava esse
# contrato.
_STEP_DESCRICOES: dict[str, str] = {
    "setup.docs_eng": "aguardando o upload dos documentos da engenharia",
    "setup.docs_complementares": "documento principal recebido; perguntando se ha documentos complementares antes de extrair",
    "setup.extrair": "documentos completos; aguardando o usuario escolher o perfil e pedir a extracao de requisitos",
    "requisitos.aprovar": "lista de requisitos extraida (rascunho) em revisao — o usuario pode editar/remover itens e aprovar (W1)",
    "analise.pronta": "requisitos aprovados; aguardando o usuario iniciar a analise",
    "analise.docs_forn": "requisitos aprovados; aguardando o upload da proposta do fornecedor para a analise",
    "analise.rodando": "analise LLM em andamento",
    "analise.erro": "a analise falhou; o usuario pode tentar de novo",
    "analise.resultado": "analise concluida; aguardando o usuario iniciar o ciclo com o fornecedor (W2)",
    "ciclo.rodada_erro": "a vinculacao/avaliacao de uma rodada do fornecedor falhou; o usuario pode tentar de novo",
    "ciclo.vinculando": "vinculando a resposta do fornecedor aos itens",
    "ciclo.vinculacao_review": "vinculos sugeridos aguardando confirmacao humana (W3)",
    "ciclo.avaliando": "avaliando as respostas do fornecedor (R2)",
    "ciclo.decidir": "itens em reavaliacao aguardando decisao humana item a item (W4)",
    "ciclo.aguardando_fornecedor": "aguardando o fornecedor responder as pendencias (carta de pendencias disponivel)",
    "verificacao.dispensada": "verificacao LLM dispensada (proposta Tipo 1); falta a validacao humana (W5)",
    "verificacao.aguardando_proposta": "aguardando a proposta final consolidada do fornecedor",
    "verificacao.rodando": "verificando a proposta final contra os acordos (R3)",
    "verificacao.validar": "verificacao concluida; falta a validacao humana (W5)",
    "caso.fechar": "tudo validado; falta fechar o caso com o desfecho (W6)",
    "caso.fechado": "caso encerrado",
    "spec.comparando": "comparando nova revisao da especificacao (R4)",
    "spec.diff_decisao": "diff da especificacao aguardando decisao do usuario (W7)",
    "spec.erro": "a comparacao da especificacao falhou",
}


def build_chat_context(
    parecer: Parecer,
    itens: list[ItemParecer],
    recomendacoes: list[Recomendacao],
    documentos: list[Documento],
    mensagens: list[MensagemChat],
    nova_mensagem: str,
    retrieved_chunks: list[DocumentoChunk] | None = None,
    retrieved_chat_memories: list["ChatMemoryHit"] | None = None,
    audit_logs: list[object] | None = None,
    include_full_text: bool = False,
    contexto_fluxo: dict | None = None,
) -> tuple[str, list[dict]]:
    """Build system prompt and contents array for Gemini multi-turn chat.

    When retrieved_chunks is provided (RAG mode), uses semantically relevant
    chunks instead of full document text. Falls back to full text when
    chunks are not available or for table regeneration.
    """

    eng_docs = eng_docs_correntes(list(documentos))
    forn_docs = [d for d in documentos if d.tipo == "fornecedor"]

    # Build compact items summary
    itens_summary = json.dumps([{
        "numero": i.numero,
        "categoria": i.categoria,
        "descricao_requisito": i.descricao_requisito[:200],
        "valor_requerido": (i.valor_requerido or "")[:150],
        "valor_fornecedor": (i.valor_fornecedor or "")[:150],
        "status": i.status,
        "justificativa_tecnica": i.justificativa_tecnica[:300] if i.justificativa_tecnica else "",
        "acao_requerida": (i.acao_requerida or "")[:200],
        "prioridade": i.prioridade,
    } for i in itens], ensure_ascii=False)

    context_parts = [
        "## CONTEXTO DO PARECER TECNICO",
        f"Numero: {parecer.numero_parecer}",
        f"Projeto: {parecer.projeto}",
        f"Fornecedor: {parecer.fornecedor}",
        f"Parecer Geral: {parecer.parecer_geral or 'N/A'}",
        f"Total Itens: {parecer.total_itens}",
        f"Aprovados: {parecer.total_aprovados} | Com Comentarios: {parecer.total_aprovados_comentarios} | Rejeitados: {parecer.total_rejeitados} | Info Ausente: {parecer.total_info_ausente} | Adicionais: {parecer.total_itens_adicionais}",
        "",
        "## DOCUMENTOS ANALISADOS",
        f"Engenharia: {', '.join(d.nome_arquivo for d in eng_docs) or 'nenhum ainda'}",
        f"Fornecedor: {', '.join(d.nome_arquivo for d in forn_docs) or 'nenhum ainda'}",
        "",
        "## TABELA DE ITENS ATUAL",
        itens_summary if itens else "(analise ainda nao executada — sem itens)",
        "",
        "## CONCLUSAO",
        parecer.conclusao or "N/A",
        "",
        "## RECOMENDACOES",
        "\n".join(f"- {r.texto}" for r in recomendacoes) or "N/A",
    ]

    # Estado do fluxo conversacional (JULIA): fase, passo ativo e draft W1
    tem_draft = bool(contexto_fluxo and contexto_fluxo.get("requisitos_draft"))
    if contexto_fluxo is not None:
        step_id = contexto_fluxo.get("step_id") or ""
        fase = contexto_fluxo.get("fase_caso") or parecer.fase_caso
        context_parts.extend([
            "",
            "## ESTADO DO FLUXO",
            f"Fase do caso: {fase}",
            f"Passo ativo: {step_id} — {_STEP_DESCRICOES.get(step_id, 'n/a')}",
        ])
        if tem_draft:
            draft_json = json.dumps(
                contexto_fluxo["requisitos_draft"], ensure_ascii=False
            )
            context_parts.extend([
                "",
                "## RASCUNHO DE REQUISITOS EM REVISAO (W1 — ainda nao aprovado)",
                "O usuario esta revisando esta lista na tela. Voce pode edita-la "
                "via bloco <acao> quando solicitado.",
                draft_json,
            ])

    if retrieved_chat_memories:
        context_parts.extend([
            "",
            "## MEMORIA SEMANTICA DO HISTORICO ANTIGO DO CHAT",
            "O usuario pediu para consultar conversas antigas. As mensagens abaixo "
            "foram recuperadas semanticamente do historico salvo deste parecer.",
            "Use estes trechos apenas quando forem relevantes para a pergunta. "
            "Ao se apoiar neles, deixe claro que a informacao veio do historico "
            "do chat e cite data/ordem quando util. Se nenhum trecho responder "
            "diretamente, diga que nao encontrou evidencia suficiente no historico.",
            "",
        ])
        for memory in retrieved_chat_memories:
            role = "Usuario" if memory.papel == "user" else "JULIA"
            created = memory.criado_em.strftime("%Y-%m-%d %H:%M")
            context_parts.append(
                f"### Mensagem #{memory.ordem} — {role} — {created} "
                f"(similaridade {memory.similarity:.3f})\n{memory.conteudo}\n"
            )

    if audit_logs:
        context_parts.extend([
            "",
            "## TRILHA DE AUDITORIA DOS ITENS",
            "Eventos registrados automaticamente quando usuario/JULIA alterou "
            "status, prioridade ou decisão de item. Use estes registros para "
            "responder perguntas como quem alterou, quando alterou e qual era "
            "o valor anterior.",
            "",
        ])
        for log in audit_logs:
            created = log.criado_em.strftime("%Y-%m-%d %H:%M") if log.criado_em else ""
            context_parts.append(
                f"- {created} | {log.usuario_email or 'sistema'} | "
                f"{log.acao} | recurso_id={log.recurso_id} | {log.detalhes or ''}"
            )

    # Include document content: either RAG chunks (preferred) or full text (fallback)
    if retrieved_chunks and not include_full_text:
        # RAG mode: include only semantically relevant chunks
        context_parts.extend([
            "",
            "## TRECHOS RELEVANTES DOS DOCUMENTOS (recuperados por relevancia semantica)",
            "Os trechos abaixo foram selecionados automaticamente como os mais relevantes "
            "para a pergunta atual. Cite SEMPRE o documento e pagina ao referenciar informacoes.",
            "Se a informacao necessaria nao estiver nestes trechos, informe que nao encontrou "
            "nos trechos disponibilizados.",
            "",
        ])
        for chunk in retrieved_chunks:
            tipo_label = "Engenharia" if chunk.tipo_documento == "engenharia" else "Fornecedor"
            page_info = f"Pagina {chunk.page_number}" if chunk.page_number else "Pagina ?"
            chunk_label = "TABELA" if chunk.chunk_type == "table" else "TEXTO"
            header = f"### [{tipo_label}] {chunk.nome_arquivo} - {page_info} ({chunk_label})"
            context_parts.append(f"{header}\n{chunk.conteudo}\n")
    else:
        # Full text mode: used for table regeneration or when RAG is not available
        context_parts.extend([
            "",
            "## TEXTO COMPLETO DOS DOCUMENTOS DA ENGENHARIA",
            "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in eng_docs
            ),
            "",
            "## TEXTO COMPLETO DOS DOCUMENTOS DO FORNECEDOR",
            "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in forn_docs
            ),
        ])

    context_msg = "\n".join(context_parts)

    if parecer.total_itens > 0:
        ack = (
            "Entendido. Tenho o contexto completo do parecer tecnico "
            f"'{parecer.numero_parecer}' para o projeto '{parecer.projeto}', "
            f"fornecedor '{parecer.fornecedor}'. "
            f"O parecer geral e '{parecer.parecer_geral}' com {parecer.total_itens} itens analisados. "
            "Estou pronta para discutir os itens, justificativas, classificacoes e "
            "conduzir o fluxo. Como posso ajudar?"
        )
    else:
        ack = (
            "Entendido. Sou a JULIA e tenho o contexto do caso "
            f"'{parecer.numero_parecer}' ({parecer.projeto} / {parecer.fornecedor}), "
            "que ainda esta nas fases iniciais do fluxo. Estou pronta para "
            "orientar os proximos passos e conversar sobre os documentos ja enviados."
        )

    contents = [
        {"role": "user", "parts": [{"text": context_msg}]},
        {"role": "model", "parts": [{"text": ack}]},
    ]

    # Add conversation history (sliding window: last 20 messages)
    recent = mensagens[-20:] if len(mensagens) > 20 else mensagens
    for msg in recent:
        role = "user" if msg.papel == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.conteudo}]})

    # Add new message
    contents.append({"role": "user", "parts": [{"text": nova_mensagem}]})

    # System prompt em camadas:
    # - draft W1 em revisao: persona JULIA + acao de requisitos (o pedido de
    #   "arrumar a lista" refere-se ao draft, nunca a tabela do parecer)
    # - pos-analise sem draft: persona de engenheiro da disciplina (SEM a
    #   metodologia/schema de analise — ver C4) + modo conversa + camada JULIA
    # - pre-analise: so a persona JULIA
    if tem_draft:
        chat_system_prompt = _JULIA_PERSONA_BASE + _JULIA_ACAO_REQUISITOS
    elif parecer.total_itens > 0:
        chat_system_prompt = (
            get_chat_persona(getattr(parecer, "disciplina", "instrumentacao"))
            + _CHAT_MODO_CONVERSA
        )
        if contexto_fluxo is not None:
            # Fluxo conversacional JULIA: NUNCA despeja JSON nem tabela; reavaliacao
            # da analise vira a acao "reanalisar" (roda R1 com barra de progresso)
            chat_system_prompt += (
                _JULIA_PERSONA_BASE + _JULIA_ACAO_ITENS + _JULIA_ACAO_REANALISAR
            )
            # Editar a LISTA de requisitos so faz sentido antes do ciclo (ANALISE)
            if parecer.fase_caso == ANALISE:
                chat_system_prompt += _JULIA_ACAO_EDITAR_REQUISITOS
            # Revisao de spec disponivel apos a analise, com o caso aberto
            if parecer.fase_caso in (ANALISE, CICLO_FORNECEDOR, VERIFICACAO_FINAL):
                chat_system_prompt += _JULIA_ACAO_REVISAO_SPEC
    else:
        chat_system_prompt = _JULIA_PERSONA_BASE
        # Pre-analise: cada passo de setup conduz a coleta de documentos / extracao
        # pela conversa (sem paineis). Anexa so a instrucao do passo ativo.
        _step_pre = contexto_fluxo.get("step_id") if contexto_fluxo else None
        if _step_pre == "setup.docs_complementares":
            chat_system_prompt += _JULIA_ACAO_COMPLEMENTARES
        elif _step_pre == "setup.extrair":
            chat_system_prompt += _JULIA_ACAO_EXTRAIR

    # Acoes de transicao de fase disponiveis no passo ativo
    if contexto_fluxo is not None:
        chat_system_prompt += _julia_acoes_transicao(
            contexto_fluxo.get("step_id") or ""
        )
    return chat_system_prompt, contents


async def call_gemini_stream_async(
    system_prompt: str,
    contents: list[dict],
    max_tokens: int = 8192,
) -> AsyncGenerator[str, None]:
    """Call Gemini streaming API, yielding text chunks as they arrive."""
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:streamGenerateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max_tokens,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST", url, params={"key": api_key, "alt": "sse"}, json=payload
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                detail = None
                try:
                    data = json.loads(body)
                    detail = data.get("error", {}).get("message")
                except Exception:
                    detail = body.decode("utf-8", errors="replace")
                raise RuntimeError(f"Erro Gemini API ({response.status_code}): {detail}")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                candidates = chunk_data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    text = part.get("text", "")
                    if text:
                        yield text


async def call_gemini_json_async(
    system_prompt: str,
    contents: list[dict],
    max_tokens: int = 65536,
) -> dict | None:
    """Chamada nao-streaming com saida JSON forcada (responseMimeType).

    Usada para reparar blocos <acao> truncados/invalidos: o modo JSON do
    Gemini garante um objeto valido e completo.
    """
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, params={"key": api_key}, json=payload)
        if response.status_code >= 400:
            logger.warning(
                "Repair JSON falhou (%s): %s",
                response.status_code,
                response.text[:300],
            )
            return None
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Repair JSON retornou conteudo invalido")
            return None


async def detectar_transicao_declarada(
    mensagem_usuario: str,
    resposta_assistente: str,
    transicoes: list[tuple[str, str]],
) -> str | None:
    """Rede de segurança: a LLM declarou executar uma transição sem emitir o bloco?

    Classificador JSON barato — garante que "Aprovado! Já estou iniciando..."
    sem bloco <acao> ainda assim execute a transição de verdade.
    """
    opcoes = "\n".join(f'- "{tipo}": {desc}' for tipo, desc in transicoes)
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": (
                        "Analise o par de mensagens abaixo. Determine se a "
                        "assistente DECLAROU que esta executando AGORA uma das "
                        "transicoes de fase a seguir (nao apenas sugerindo ou "
                        "perguntando):\n"
                        f"{opcoes}\n\n"
                        f"MENSAGEM DO USUARIO:\n{mensagem_usuario[:2000]}\n\n"
                        f"RESPOSTA DA ASSISTENTE:\n{resposta_assistente[:4000]}\n\n"
                        'Responda APENAS o JSON {"tipo": "<tipo>"} ou {"tipo": null}.'
                    )
                }
            ],
        }
    ]
    data = await call_gemini_json_async(
        "Voce e um classificador estrito. Responda somente JSON valido.",
        contents,
        max_tokens=64,
    )
    tipo = (data or {}).get("tipo")
    return tipo if tipo in {t for t, _ in transicoes} else None


def parse_acao_block(raw: str) -> dict | None:
    """Extrai o JSON de um bloco <acao>, tolerando fences markdown e ruido."""
    raw = raw.strip()
    # tolera ```json ... ``` dentro do bloco
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
