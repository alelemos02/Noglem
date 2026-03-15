"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { patecApi } from "@/lib/patec-api";

export default function NovoParecerPage() {
  const router = useRouter();
  const [numeroParecer, setNumeroParecer] = useState("");
  const [projeto, setProjeto] = useState("");
  const [fornecedor, setFornecedor] = useState("");
  const [revisao, setRevisao] = useState("0");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const canCreate = numeroParecer.trim() && projeto.trim() && fornecedor.trim();

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
      });
      router.push(`/dashboard/parecer-tecnico/${parecer.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar parecer");
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <Link
          href="/dashboard/parecer-tecnico"
          className="text-sm text-text-tertiary hover:text-text-secondary"
        >
          ← Voltar para listagem
        </Link>
        <h1 className="mt-2 font-heading text-2xl font-bold text-text-primary">
          Novo Parecer Técnico
        </h1>
      </div>

      <div className="rounded-lg border border-border bg-surface p-6 space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Número do Parecer *
          </label>
          <Input
            value={numeroParecer}
            onChange={(e) => setNumeroParecer(e.target.value)}
            placeholder="Ex: SCMD-001"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Projeto *
          </label>
          <Input
            value={projeto}
            onChange={(e) => setProjeto(e.target.value)}
            placeholder="Ex: TGN"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Fornecedor *
          </label>
          <Input
            value={fornecedor}
            onChange={(e) => setFornecedor(e.target.value)}
            placeholder="Ex: ABB"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            Revisão
          </label>
          <Input
            value={revisao}
            onChange={(e) => setRevisao(e.target.value)}
            placeholder="0"
          />
        </div>

        {error && (
          <div className="rounded-lg bg-error-muted p-3 text-sm text-error-text">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <Link href="/dashboard/parecer-tecnico">
            <Button variant="outline">Cancelar</Button>
          </Link>
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={!canCreate || creating}
          >
            {creating ? "Criando..." : "Criar Parecer"}
          </Button>
        </div>
      </div>
    </div>
  );
}
