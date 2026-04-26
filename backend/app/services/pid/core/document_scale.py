"""DocumentScale: contexto de escala por página para limiares espaciais.

Todos os valores-base neste código estão calibrados para A3 paisagem
(841.9 × 595.3 pontos PDF a 72 DPI). Quando um documento usa um tamanho
de página diferente, cada limiar deve ser multiplicado pela razão entre
a largura efetiva real e a largura de referência.

Uso típico:
    scale = DocumentScale.from_page(page_width, page_height)
    gap_x = scale.px(5.0)   # em vez do literal 5.0
    radius = scale.px(200.0) # distância máxima de associação
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# A3 paisagem em pontos PDF (base de referência)
REFERENCE_PAGE_WIDTH: float = 841.9
REFERENCE_PAGE_HEIGHT: float = 595.3

# Tamanhos padrão ISO em pontos PDF (largura × altura em orientação paisagem)
PAPER_SIZES = {
    "A0": (3370.4, 2383.9),
    "A1": (2383.9, 1683.8),
    "A2": (1683.8, 1190.6),
    "A3": (841.9, 595.3),
    "A4": (595.3, 419.5),
}


@dataclass
class DocumentScale:
    """Contexto de escala derivado das dimensões reais de uma página PDF.

    Attributes:
        page_width:    Largura real da página em pontos PDF.
        page_height:   Altura real da página em pontos PDF.
        scale_factor:  Razão effective_width / REFERENCE_PAGE_WIDTH.
                       1.0 = exatamente A3 paisagem.
                       2.0 = documento duas vezes mais largo (território A1/A0).
                       0.7 = documento menor que A3 (A4).
    """
    page_width: float
    page_height: float
    scale_factor: float
    _calibrated_symbol_size: Optional[float] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_page(
        cls,
        page_width: float,
        page_height: float,
        reference_width: float = REFERENCE_PAGE_WIDTH,
    ) -> "DocumentScale":
        """Cria um DocumentScale a partir das dimensões reais da página.

        Usa o maior valor entre largura e altura como 'largura efetiva',
        tornando o cálculo correto tanto para paisagem quanto para retrato.

        Args:
            page_width:      Largura da página em pontos PDF.
            page_height:     Altura da página em pontos PDF.
            reference_width: Largura de referência (padrão: A3 paisagem).

        Returns:
            Instância de DocumentScale pronta para uso.
        """
        effective_width = max(page_width, page_height)
        # Clampa entre 0.5× e 4× para evitar limiares absurdos em PDFs corrompidos
        scale = max(0.5, min(4.0, effective_width / reference_width))

        instance = cls(
            page_width=page_width,
            page_height=page_height,
            scale_factor=scale,
        )
        logger.debug(
            "DocumentScale: %.0fx%.0f pt → scale=%.3f (%s)",
            page_width, page_height, scale, instance.paper_size_name,
        )
        return instance

    # ------------------------------------------------------------------
    # Método central de escala
    # ------------------------------------------------------------------

    def px(self, base_value: float) -> float:
        """Escala um valor-base para as dimensões reais do documento.

        Args:
            base_value: Limiar/distância calibrado para A3 paisagem.

        Returns:
            O limiar ajustado ao tamanho real da página.
        """
        return base_value * self.scale_factor

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def is_large_format(self) -> bool:
        """True se a página for A1 ou maior (scale_factor > ~1.4)."""
        return self.scale_factor > 1.4

    @property
    def paper_size_name(self) -> str:
        """Tamanho de papel estimado para logging."""
        effective = max(self.page_width, self.page_height)
        for name, (w, h) in PAPER_SIZES.items():
            ref = max(w, h)
            if abs(effective - ref) / ref < 0.05:
                return name
        return f"custom({self.page_width:.0f}x{self.page_height:.0f})"

    # ------------------------------------------------------------------
    # Auto-calibração por símbolo real
    # ------------------------------------------------------------------

    def auto_calibrate(self, rects: list) -> None:
        """Refina scale_factor pelo tamanho mediano de quadrados DCS na página.

        Varre todos os retângulos da página e coleta os de proporção
        aproximadamente quadrada dentro de uma faixa plausível de balão.
        Se encontrar pelo menos 3, ajusta o scale_factor para que
        px(35.0) corresponda ao tamanho mediano detectado.

        Se a página não tiver quadrados DCS (todos os instrumentos são
        físicos/campo), a calibração é ignorada e scale_factor permanece
        inalterado.

        Args:
            rects: Lista de dicts de retângulos de pdfplumber (page.rects).
        """
        if not rects:
            return

        sizes = []
        for r in rects:
            try:
                w = float(r.get("x1", 0)) - float(r.get("x0", 0))
                h = float(r.get("bottom", 0)) - float(r.get("top", 0))
            except (TypeError, ValueError):
                continue
            if w <= 0 or h <= 0:
                continue
            # Deve ser aproximadamente quadrado (proporção 0.6–1.6)
            if not (0.6 < w / h < 1.6):
                continue
            size = (w + h) / 2
            # Faixa plausível: 10px a 150px (cobre A4 até A0)
            if 10.0 < size < 150.0:
                sizes.append(size)

        if len(sizes) < 3:
            logger.debug("auto_calibrate: quadrados insuficientes (%d)", len(sizes))
            return

        sizes.sort()
        median_size = sizes[len(sizes) // 2]

        # 35px é o ponto médio da faixa A3 (25-50px → meio ≈ 37.5, usamos 35)
        base_balloon_size = 35.0
        new_scale = max(0.5, min(4.0, median_size / base_balloon_size))

        logger.info(
            "auto_calibrate: mediana=%.1fpx → scale %.3f → %.3f",
            median_size, self.scale_factor, new_scale,
        )
        self.scale_factor = new_scale
        self._calibrated_symbol_size = median_size

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        cal = f", calibrado={self._calibrated_symbol_size:.1f}px" if self._calibrated_symbol_size else ""
        return (
            f"DocumentScale(pagina={self.page_width:.0f}x{self.page_height:.0f}, "
            f"scale={self.scale_factor:.3f}, tamanho={self.paper_size_name}{cal})"
        )


def _s(scale: Optional[DocumentScale], base: float) -> float:
    """Helper: escala valor-base se scale fornecido, caso contrário retorna base.

    Usado em todos os módulos para retrocompatibilidade: ao chamar funções
    sem scale (testes, scripts legados), os valores-base literais são usados.

    Args:
        scale: Instância de DocumentScale, ou None.
        base:  Valor-base calibrado para A3.

    Returns:
        base * scale_factor se scale não for None, senão base.
    """
    if scale is None:
        return base
    return scale.px(base)
