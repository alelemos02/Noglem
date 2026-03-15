"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  patecApi,
  type RevisaoResponse,
  type RevisaoCompareResponse,
} from "@/lib/patec-api";

interface RevisoesPanelProps {
  parecerId: string;
}

export function RevisoesPanel({ parecerId }: RevisoesPanelProps) {
  const [revisoes, setRevisoes] = useState<RevisaoResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [compareResult, setCompareResult] =
    useState<RevisaoCompareResponse | null>(null);
  const [selectedRevs, setSelectedRevs] = useState<
    [number | null, number | null]
  >([null, null]);

  const loadRevisoes = useCallback(async () => {
    try {
      const data = await patecApi.revisoes.list(parecerId);
      setRevisoes(data.items);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [parecerId]);

  useEffect(() => {
    loadRevisoes();
  }, [loadRevisoes]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      await patecApi.revisoes.create(parecerId, {
        motivo: motivo || undefined,
      });
      setMotivo("");
      setShowForm(false);
      await loadRevisoes();
    } catch {
      // handle error
    } finally {
      setCreating(false);
    }
  };

  const handleCompare = async () => {
    if (selectedRevs[0] === null || selectedRevs[1] === null) return;
    setComparing(true);
    try {
      const result = await patecApi.revisoes.comparar(
        parecerId,
        selectedRevs[0],
        selectedRevs[1]
      );
      setCompareResult(result);
    } catch {
      // handle error
    } finally {
      setComparing(false);
    }
  };

  const toggleRevSelection = (revNum: number) => {
    setSelectedRevs((prev) => {
      if (prev[0] === revNum) return [null, prev[1]];
      if (prev[1] === revNum) return [prev[0], null];
      if (prev[0] === null) return [revNum, prev[1]];
      return [prev[0], revNum];
    });
    setCompareResult(null);
  };

  if (loading) {
    return (
      <p className="text-sm text-text-secondary">Carregando revisoes...</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">
          {revisoes.length} revisao(oes) salva(s)
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancelar" : "Salvar Revisao"}
        </Button>
      </div>

      {showForm && (
        <div className="flex items-center gap-2">
          <Input
            placeholder="Motivo da revisao (opcional)"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            className="flex-1"
          />
          <Button onClick={handleCreate} disabled={creating} size="sm">
            {creating ? "Salvando..." : "Confirmar"}
          </Button>
        </div>
      )}

      {revisoes.length > 1 && (
        <div className="flex items-center gap-2">
          <p className="text-xs text-text-secondary">
            Selecione 2 revisoes para comparar:
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCompare}
            disabled={
              selectedRevs[0] === null ||
              selectedRevs[1] === null ||
              comparing
            }
          >
            {comparing ? "Comparando..." : "Comparar"}
          </Button>
        </div>
      )}

      <div className="space-y-2">
        {revisoes.map((rev) => {
          const isSelected =
            selectedRevs[0] === rev.numero_revisao ||
            selectedRevs[1] === rev.numero_revisao;

          return (
            <div
              key={rev.id}
              className={`flex cursor-pointer items-center justify-between rounded border p-3 text-sm transition-colors ${
                isSelected
                  ? "border-accent bg-accent/10"
                  : "border-border hover:bg-surface-hover"
              }`}
              onClick={() => toggleRevSelection(rev.numero_revisao)}
            >
              <div>
                <span className="font-medium text-text-primary">
                  Revisao {rev.numero_revisao}
                </span>
                {rev.motivo && (
                  <span className="ml-2 text-text-secondary">
                    - {rev.motivo}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-text-secondary">
                <span>
                  {rev.total_itens} itens | {rev.parecer_geral || "Pendente"}
                </span>
                <span>
                  {new Date(rev.criado_em).toLocaleDateString("pt-BR", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {compareResult && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <h4 className="mb-3 text-sm font-bold text-text-primary">
            Comparacao: Rev {compareResult.revisao_a.numero_revisao} vs Rev{" "}
            {compareResult.revisao_b.numero_revisao}
          </h4>
          <div className="space-y-3 text-sm">
            {Object.keys(compareResult.diferencas.resumo).length > 0 && (
              <div>
                <p className="mb-1 font-medium text-text-primary">
                  Alteracoes no resumo:
                </p>
                {Object.entries(compareResult.diferencas.resumo).map(
                  ([campo, diff]) => (
                    <p key={campo} className="text-xs text-text-secondary">
                      <span className="font-medium">{campo}:</span>{" "}
                      <span className="text-red-400">
                        {String(diff.de)}
                      </span>{" "}
                      →{" "}
                      <span className="text-green-400">
                        {String(diff.para)}
                      </span>
                    </p>
                  )
                )}
              </div>
            )}

            <div className="flex gap-4 text-xs">
              {compareResult.diferencas.itens_adicionados > 0 && (
                <span className="text-green-400">
                  +{compareResult.diferencas.itens_adicionados} itens
                  adicionados
                </span>
              )}
              {compareResult.diferencas.itens_removidos > 0 && (
                <span className="text-red-400">
                  -{compareResult.diferencas.itens_removidos} itens removidos
                </span>
              )}
              {compareResult.diferencas.itens_alterados.length > 0 && (
                <span className="text-yellow-400">
                  {compareResult.diferencas.itens_alterados.length} itens
                  alterados
                </span>
              )}
            </div>

            {compareResult.diferencas.itens_alterados.length > 0 && (
              <div>
                <p className="mb-1 font-medium text-text-primary">
                  Itens alterados:
                </p>
                {compareResult.diferencas.itens_alterados
                  .slice(0, 10)
                  .map((item) => (
                    <div
                      key={item.numero}
                      className="mb-1 ml-2 border-l-2 border-yellow-600/50 pl-2 text-xs"
                    >
                      <span className="font-medium text-text-primary">
                        Item {item.numero}:
                      </span>{" "}
                      {Object.entries(item.alteracoes).map(([key, diff]) => (
                        <span key={key} className="mr-2 text-text-secondary">
                          {key}:{" "}
                          <span className="text-red-400">
                            {String(diff.de)}
                          </span>{" "}
                          →{" "}
                          <span className="text-green-400">
                            {String(diff.para)}
                          </span>
                        </span>
                      ))}
                    </div>
                  ))}
                {compareResult.diferencas.itens_alterados.length > 10 && (
                  <p className="ml-2 text-xs text-text-tertiary">
                    ... e mais{" "}
                    {compareResult.diferencas.itens_alterados.length - 10}{" "}
                    alteracoes
                  </p>
                )}
              </div>
            )}

            {Object.keys(compareResult.diferencas.resumo).length === 0 &&
              compareResult.diferencas.itens_adicionados === 0 &&
              compareResult.diferencas.itens_removidos === 0 &&
              compareResult.diferencas.itens_alterados.length === 0 && (
                <p className="text-text-secondary">
                  Nenhuma diferenca encontrada entre as revisoes.
                </p>
              )}
          </div>
        </div>
      )}
    </div>
  );
}
