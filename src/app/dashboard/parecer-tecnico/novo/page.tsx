"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { patecApi, type ReportLanguage } from "@/lib/patec-api";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type DisciplinaKey = "instrumentacao" | "eletrico" | "civil" | "mecanico" | "tubulacao";

interface Disciplina {
  key: DisciplinaKey;
  label: string;
  descricao: string;
  ativo: boolean;
}

const DISCIPLINAS: Disciplina[] = [
  {
    key: "instrumentacao",
    label: "Instrumentação",
    descricao: "Transmissores, válvulas, analisadores, malhas de controle",
    ativo: true,
  },
  {
    key: "eletrico",
    label: "Elétrico",
    descricao: "Painéis, cabos, motores, CCMs, proteções elétricas",
    ativo: true,
  },
  {
    key: "civil",
    label: "Civil",
    descricao: "Estruturas, fundações, obras civis",
    ativo: false,
  },
  {
    key: "mecanico",
    label: "Mecânico",
    descricao: "Vasos, trocadores, bombas, compressores",
    ativo: false,
  },
  {
    key: "tubulacao",
    label: "Tubulação",
    descricao: "Tubos, flanges, válvulas, suportes",
    ativo: false,
  },
];

const IDIOMAS_RELATORIO: { value: ReportLanguage; label: string }[] = [
  { value: "pt", label: "Português" },
  { value: "es", label: "Espanhol" },
  { value: "en", label: "Inglês" },
];

export default function NovoParecerPage() {
  const router = useRouter();
  const [disciplina, setDisciplina] = useState<DisciplinaKey | null>(null);
  const [numeroParecer, setNumeroParecer] = useState("");
  const [projeto, setProjeto] = useState("");
  const [fornecedor, setFornecedor] = useState("");
  const [revisao, setRevisao] = useState("0");
  const [idiomaRelatorio, setIdiomaRelatorio] = useState<ReportLanguage>("pt");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const canCreate = disciplina && numeroParecer.trim() && projeto.trim() && fornecedor.trim();

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    setError("");
    try {
      const parecer = await patecApi.pareceres.create({
        numero_parecer: numeroParecer.trim(),
        projeto: projeto.trim(),
        fornecedor: fornecedor.trim(),
        revisao: revisao.trim() || "0",
        disciplina: disciplina!,
        idioma_relatorio: idiomaRelatorio,
      });
      router.push(`/dashboard/parecer-tecnico/${parecer.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar parecer");
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Novo Parecer Técnico"
        description="Selecione a disciplina, envie os documentos e configure a análise."
        backHref="/dashboard/parecer-tecnico"
        backLabel="Pareceres"
        className="mb-0"
      />

      {/* Disciplina selector */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-fg-muted">
          Selecione a disciplina *
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {DISCIPLINAS.map((d) => {
            const isSelected = disciplina === d.key;
            return (
              <button
                key={d.key}
                type="button"
                disabled={!d.ativo}
                onClick={() => d.ativo && setDisciplina(d.key)}
                className={cn(
                  "relative flex flex-col items-start gap-1 rounded-lg border p-4 text-left transition-all",
                  d.ativo
                    ? "cursor-pointer hover:border-edge-strong hover:bg-surface-2"
                    : "cursor-not-allowed opacity-50",
                  isSelected
                    ? "border-accent bg-accent-subtle"
                    : "border-edge bg-surface-1"
                )}
              >
                {!d.ativo && (
                  <Badge variant="secondary" className="absolute right-2 top-2 text-xs">
                    Em breve
                  </Badge>
                )}
                <span className={cn(
                  "text-sm font-semibold",
                  isSelected ? "text-accent" : "text-fg"
                )}>
                  {d.label}
                </span>
                <span className="text-xs text-fg-subtle leading-snug">
                  {d.descricao}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Form fields */}
      <div className="rounded-lg border border-edge bg-surface-1 p-6 space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-fg-muted">
            Número do Parecer *
          </label>
          <Input
            value={numeroParecer}
            onChange={(e) => setNumeroParecer(e.target.value)}
            placeholder="Ex: SCMD-001"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-fg-muted">
            Projeto *
          </label>
          <Input
            value={projeto}
            onChange={(e) => setProjeto(e.target.value)}
            placeholder="Ex: TGN"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-fg-muted">
            Fornecedor *
          </label>
          <Input
            value={fornecedor}
            onChange={(e) => setFornecedor(e.target.value)}
            placeholder="Ex: ABB"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-fg-muted">
            Revisão
          </label>
          <Input
            value={revisao}
            onChange={(e) => setRevisao(e.target.value)}
            placeholder="0"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-fg-muted">
            Idioma do Relatório
          </label>
          <Select
            value={idiomaRelatorio}
            onValueChange={(v) => setIdiomaRelatorio(v as ReportLanguage)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {IDIOMAS_RELATORIO.map((idioma) => (
                <SelectItem key={idioma.value} value={idioma.value}>
                  {idioma.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {error && <Alert variant="danger">{error}</Alert>}

        <div className="flex gap-3 pt-2">
          <Link href="/dashboard/parecer-tecnico">
            <Button variant="outline">Cancelar</Button>
          </Link>
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={!canCreate}
            loading={creating}
          >
            {creating ? "Criando..." : "Criar parecer"}
          </Button>
        </div>
      </div>
    </div>
  );
}
