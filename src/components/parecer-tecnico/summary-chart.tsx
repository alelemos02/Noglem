"use client";

interface SummaryChartProps {
  aprovados: number;
  aprovadosComentarios: number;
  rejeitados: number;
  infoAusente: number;
  itensAdicionais: number;
}

const SEGMENTS = [
  { key: "aprovados", label: "Aprovados (A)", color: "#22C55E", prop: "aprovados" as const },
  { key: "comentarios", label: "Aprov. c/ Com. (B)", color: "#EAB308", prop: "aprovadosComentarios" as const },
  { key: "rejeitados", label: "Rejeitados (C)", color: "#EF4444", prop: "rejeitados" as const },
  { key: "ausente", label: "Info Ausente (D)", color: "#6B7280", prop: "infoAusente" as const },
  { key: "adicionais", label: "Adicionais (E)", color: "#3B82F6", prop: "itensAdicionais" as const },
];

export function SummaryChart(props: SummaryChartProps) {
  const total = props.aprovados + props.aprovadosComentarios + props.rejeitados + props.infoAusente + props.itensAdicionais;
  if (total === 0) return null;

  const parts: string[] = [];
  let acc = 0;
  for (const seg of SEGMENTS) {
    const val = props[seg.prop];
    if (val === 0) continue;
    const pct = (val / total) * 100;
    parts.push(`${seg.color} ${acc}% ${acc + pct}%`);
    acc += pct;
  }

  const gradient = `conic-gradient(${parts.join(", ")})`;

  return (
    <div className="flex items-center gap-6">
      <div className="relative h-28 w-28 flex-shrink-0">
        <div
          className="h-full w-full rounded-full"
          style={{ background: gradient }}
        />
        <div className="absolute inset-3 flex items-center justify-center rounded-full bg-bg-primary">
          <span className="text-xl font-bold text-text-primary">{total}</span>
        </div>
      </div>
      <div className="space-y-1">
        {SEGMENTS.map((seg) => {
          const val = props[seg.prop];
          if (val === 0) return null;
          return (
            <div key={seg.key} className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: seg.color }} />
              <span className="text-xs text-text-secondary">
                {seg.label}: {val}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
