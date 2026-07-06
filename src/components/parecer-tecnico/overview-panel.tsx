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
      <div className="rounded-lg border border-edge bg-surface-1 p-6">
        <h2 className="mb-4 text-lg font-bold text-fg">
          Resumo Executivo
        </h2>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          {/* Left: stats + chart */}
          <div className="shrink-0 space-y-4">
            <div className="grid grid-cols-3 gap-x-6 gap-y-3">
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-fg">
                  {parecer.total_itens}
                </p>
                <p className="text-xs text-fg-muted">Total</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-success">
                  {parecer.total_aprovados}
                </p>
                <p className="text-xs text-fg-muted">Aprovados</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-warning">
                  {parecer.total_aprovados_comentarios}
                </p>
                <p className="text-xs text-fg-muted">Aprov. c/ Com.</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-danger">
                  {parecer.total_rejeitados}
                </p>
                <p className="text-xs text-fg-muted">Rejeitados</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-fg-subtle">
                  {parecer.total_info_ausente}
                </p>
                <p className="text-xs text-fg-muted">Info Ausente</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold font-mono tabular-nums text-info">
                  {parecer.total_itens_adicionais}
                </p>
                <p className="text-xs text-fg-muted">Adicionais</p>
              </div>
            </div>

            <SummaryChart
              aprovados={parecer.total_aprovados}
              aprovadosComentarios={parecer.total_aprovados_comentarios}
              rejeitados={parecer.total_rejeitados}
              infoAusente={parecer.total_info_ausente}
              itensAdicionais={parecer.total_itens_adicionais}
            />
          </div>

          {/* Divider */}
          <div className="hidden lg:block lg:self-stretch lg:border-l lg:border-edge" />

          {/* Right: executive summary text */}
          {parecer.comentario_geral && (
            <p className="flex-1 text-sm leading-relaxed text-fg">
              {parecer.comentario_geral}
            </p>
          )}
        </div>
      </div>

      {/* Metadata */}
      <div className="rounded-lg border border-edge bg-surface-1 p-6">
        <h3 className="mb-3 text-sm font-bold text-fg">
          Informacoes do Parecer
        </h3>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs text-fg-muted">Projeto</p>
            <p className="text-sm font-medium text-fg">
              {parecer.projeto}
            </p>
          </div>
          <div>
            <p className="text-xs text-fg-muted">Fornecedor</p>
            <p className="text-sm font-medium text-fg">
              {parecer.fornecedor}
            </p>
          </div>
          <div>
            <p className="text-xs text-fg-muted">Revisao</p>
            <p className="text-sm font-medium text-fg">
              {parecer.revisao}
            </p>
          </div>
          <div>
            <p className="text-xs text-fg-muted">Data</p>
            <p className="text-sm font-medium text-fg">
              {new Date(parecer.criado_em).toLocaleDateString("pt-BR")}
            </p>
          </div>
        </div>
      </div>

      {/* Conclusion & Recommendations */}
      {(parecer.conclusao || recomendacoes.length > 0) && (
        <div className="space-y-4 rounded-lg border border-edge bg-surface-1 p-6">
          <h3 className="text-sm font-bold text-fg">
            Conclusao e Recomendacoes
          </h3>
          {parecer.conclusao && (
            <div>
              <p className="mb-1 text-xs font-semibold text-fg-muted">
                Conclusao
              </p>
              <p className="whitespace-pre-line text-sm text-fg">
                {parecer.conclusao}
              </p>
            </div>
          )}
          {recomendacoes.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-fg-muted">
                Recomendacoes
              </p>
              <ul className="list-inside list-disc space-y-1">
                {recomendacoes.map((rec) => (
                  <li key={rec.id} className="text-sm text-fg">
                    {rec.texto}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Document Numbers Reference */}
      {documentos.length > 0 && (
        <div className="rounded-lg border border-edge bg-surface-1 p-6">
          <h3 className="mb-3 text-sm font-bold text-fg">
            Documentos Carregados
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-semibold text-fg-muted">
                Engenharia ({documentos.filter((d) => d.tipo === "engenharia").length})
              </p>
              {documentos.filter((d) => d.tipo === "engenharia").length > 0 ? (
                <ul className="space-y-1">
                  {documentos
                    .filter((d) => d.tipo === "engenharia")
                    .map((doc) => (
                      <li key={doc.id} className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-xs text-fg">
                          {doc.nome_arquivo}
                        </span>
                        {doc.tamanho_bytes && (
                          <span className="text-xs text-fg-subtle">
                            ({(doc.tamanho_bytes / 1024).toFixed(0)} KB)
                          </span>
                        )}
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-xs text-fg-subtle">Nenhum documento</p>
              )}
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold text-fg-muted">
                Fornecedor ({documentos.filter((d) => d.tipo === "fornecedor").length})
              </p>
              {documentos.filter((d) => d.tipo === "fornecedor").length > 0 ? (
                <ul className="space-y-1">
                  {documentos
                    .filter((d) => d.tipo === "fornecedor")
                    .map((doc) => (
                      <li key={doc.id} className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-xs text-fg">
                          {doc.nome_arquivo}
                        </span>
                        {doc.tamanho_bytes && (
                          <span className="text-xs text-fg-subtle">
                            ({(doc.tamanho_bytes / 1024).toFixed(0)} KB)
                          </span>
                        )}
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-xs text-fg-subtle">Nenhum documento</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Document Upload */}
      <div className="rounded-lg border border-edge bg-surface-1 p-6">
        <h3 className="mb-3 text-sm font-bold text-fg">
          Upload de Documentos
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
      <div className="rounded-lg border border-edge bg-surface-1 p-6">
        <h3 className="mb-3 text-sm font-bold text-fg">
          Historico de Revisoes
        </h3>
        <RevisoesPanel parecerId={parecer.id} />
      </div>
    </div>
  );
}
