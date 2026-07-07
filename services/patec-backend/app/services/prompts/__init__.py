"""
Prompts LLM do PATEC, organizados por operacao do fluxo do caso tecnico:

  - analise.py   — analise comparativa requisitos vs proposta (R1/W2)
  - extracao.py  — extracao de requisitos dos docs de engenharia (blocos 8-10, W1)

Modulos futuros: vinculacao.py (W3), avaliacao.py (R2), verificacao.py (R3/W5),
spec_diff.py (R4/W7).
"""

from app.services.prompts.analise import (  # noqa: F401
    APPROVED_ITEMS_CONTEXT,
    CHUNK_USER_PROMPT_TEMPLATE,
    FIELD_OPTIMIZATION_SYSTEM,
    PROFILE_INTEGRAL_TEMPLATE,
    PROFILE_ITEM_LIMIT_TEMPLATE,
    REDUCE_PROMPT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_ELETRICO,
    SYSTEM_PROMPT_INSTRUMENTACAO,
    USER_PROMPT_TEMPLATE,
    get_report_language_instruction,
    get_system_prompt,
)
from app.services.prompts.extracao import (  # noqa: F401
    EXTRACAO_SYSTEM_PROMPT,
    EXTRACAO_USER_PROMPT_TEMPLATE,
)
