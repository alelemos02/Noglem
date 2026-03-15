"use client";

import { SummaryChart } from "./summary-chart";
import { FileUploadZone } from "./file-upload-zone";
import { RevisoesPanel } from "./revisoes-panel";
import { useWorkspace } from "./workspace-context";

export function OverviewPanel() {
  const { parecer, recomendacoes, documentos, loadDocumentos } = useWorkspace();

  if (!parecer) return null;

  return (
    <div className="space-y-6 p-6">
      {/* Summary */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">
          Resumo Executivo
        </h2>

        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-text-primary">
                {parecer.total_itens}
              </p>
              <p className="text-xs text-text-secondary">Total</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-400">
                {parecer.total_aprovados}
              </p>
              <p className="text-xs text-text-secondary">Aprovados</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-400">
                {parecer.total_aprovados_comentarios}
              </p>
              <p className="text-xs text-text-secondary">Aprov. c/ Com.</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-400">
                {parecer.total_rejeitados}
              </p>
              <p className="text-xs text-text-secondary">Rejeitados</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-400">
                {parecer.total_info_ausente}
              </p>
              <p className="text-xs text-text-secondary">Info Ausente</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-400">
                {parecer.total_itens_adicionais}
              </p>
              <p className="text-xs text-text-secondary">Adicionais</p>
            </div>
          </div>

          {/* Chart */}
          <SummaryChart
            aprovados={parecer.total_aprovados}
            aprovadosComentarios={parecer.total_aprovados_comentarios}
            rejeitados={parecer.total_rejeitados}
            infoAusente={parecer.total_info_ausente}
            itensAdicionais={parecer.total_itens_adicionais}
          />
        </div>

        {parecer.comentario_geral && (
          <>
            <div className="my-4 border-t border-border" />
            <p className="text-sm text-text-primary">
              {parecer.comentario_geral}
            </p>
          </>
        )}
      </div>

      {/* Metadata */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h3 className="mb-3 text-sm font-bold text-text-primary">
          Informacoes do Parecer
        </h3>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs text-text-secondary">Projeto</p>
            <p className="text-sm font-medium text-text-primary">
              {parecer.projeto}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Fornecedor</p>
            <p className="text-sm font-medium text-text-primary">
              {parecer.fornecedor}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Revisao</p>
            <p className="text-sm font-medium text-text-primary">
              {parecer.revisao}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Data</p>
            <p className="text-sm font-medium text-text-primary">
              {new Date(parecer.criado_em).toLocaleDateString("pt-BR")}
            </p>
          </div>
        </div>
      </div>

      {/* Conclusion & Recommendations */}
      {(parecer.conclusao || recomendacoes.length > 0) && (
        <div className="space-y-4 rounded-lg border border-border bg-surface p-6">
          <h3 className="text-sm font-bold text-text-primary">
            Conclusao e Recomendacoes
          </h3>
          {parecer.conclusao && (
            <div>
              <p className="mb-1 text-xs font-semibold text-text-secondary">
                Conclusao
              </p>
              <p className="whitespace-pre-line text-sm text-text-primary">
                {parecer.conclusao}
              </p>
            </div>
          )}
          {recomendacoes.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-text-secondary">
                Recomendacoes
              </p>
              <ul className="list-inside list-disc space-y-1">
                {recomendacoes.map((rec) => (
                  <li key={rec.id} className="text-sm text-text-primary">
                    {rec.texto}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Documents */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h3 className="mb-3 text-sm font-bold text-text-primary">
          Documentos
        </h3>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <FileUploadZone
            parecerId={parecer.id}
            tipo="engenharia"
            label="Documentos da Engenharia"
            documentos={documentos}
            onUploadComplete={loadDocumentos}
          />
          <FileUploadZone
            parecerId={parecer.id}
            tipo="fornecedor"
            label="Documentos do Fornecedor"
            documentos={documentos}
            onUploadComplete={loadDocumentos}
          />
        </div>
      </div>

      {/* Revision history */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h3 className="mb-3 text-sm font-bold text-text-primary">
          Historico de Revisoes
        </h3>
        <RevisoesPanel parecerId={parecer.id} />
      </div>
    </div>
  );
}
