"use client";

/**
 * StepWidget — mapeia o passo ativo da conversa para o widget interativo.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useConversation } from "./conversation-provider";
import { WidgetFrame } from "./widgets/widget-frame";
import { UploadWidget } from "./widgets/upload-widget";
import { RequisitosWidget } from "./widgets/requisitos-widget";
import { ProgressWidget } from "./widgets/progress-widget";
import { AnaliseResultadoWidget } from "./widgets/analise-resultado-widget";
import { VinculacaoWidget } from "./widgets/vinculacao-widget";
import { ItemDecisionWidget } from "./widgets/item-decision-widget";
import { AguardandoWidget } from "./widgets/aguardando-widget";
import { RodadaWidget } from "./widgets/rodada-widget";
import { VerificacaoWidget } from "./widgets/verificacao-widget";
import { FecharWidget } from "./widgets/fechar-widget";
import { ExportWidget } from "./widgets/export-widget";
import { SpecRevisionWidget } from "./widgets/spec-revision-widget";

// Passo setup.docs_complementares: anexar referências/normas (opcional) e seguir.
// O documento principal já entrou; complementares são só apoio. O usuário também
// pode resolver isso pela conversa ("não tenho", "pode seguir").
function ComplementaresWidget() {
  const { confirmarComplementares } = useConversation();
  const [pending, setPending] = useState(false);
  return (
    <div className="space-y-3">
      <UploadWidget
        tipo="anexo_engenharia"
        hint="Documentos complementares (referências técnicas, normas) — opcional"
      />
      <WidgetFrame>
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-fg-subtle">
            Anexe os complementares (se houver) ou prossiga sem eles.
          </p>
          <Button
            onClick={async () => {
              setPending(true);
              try {
                await confirmarComplementares();
              } finally {
                setPending(false);
              }
            }}
            loading={pending}
            disabled={pending}
          >
            Não tenho / Prosseguir
          </Button>
        </div>
      </WidgetFrame>
    </div>
  );
}

// Passo setup.extrair: a escolha de quantos requisitos extrair acontece na
// conversa (não mais num card de perfis). Aqui só mostramos o progresso da
// extração enquanto ela roda; fora disso, nada — o chat conduz.
function ExtrairRequisitosWidget() {
  const { extracting } = useConversation();
  if (!extracting) return null;
  return (
    <WidgetFrame>
      <div className="flex items-center gap-3 text-sm text-fg-muted">
        <Spinner size="xs" className="text-accent" />
        Lendo o documento e extraindo os requisitos…
      </div>
    </WidgetFrame>
  );
}

function RetryAnaliseWidget() {
  const { startAnalysis, snapshot } = useConversation();
  return (
    <WidgetFrame>
      <Button onClick={() => startAnalysis().catch(() => {})}>
        {snapshot && snapshot.parecer.total_itens > 0
          ? "Tentar análise novamente"
          : "Iniciar análise"}
      </Button>
    </WidgetFrame>
  );
}

function RodadaErroWidget() {
  const { step } = useConversation();
  const detalhe = step?.rodada?.erro_detalhe;
  return (
    <div className="space-y-2">
      {detalhe && (
        <div className="rounded-lg border border-danger/30 bg-danger-subtle px-4 py-3">
          <p className="text-xs text-danger-text">{detalhe}</p>
        </div>
      )}
      <RodadaWidget />
    </div>
  );
}

function SpecErroWidget() {
  const { step, descartarSpec, recompararSpec } = useConversation();
  const versao = step?.specVersao;
  if (!versao) return null;
  return (
    <WidgetFrame>
      {versao.erro_detalhe && (
        <p className="mb-3 text-xs text-danger-text">{versao.erro_detalhe}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={() => recompararSpec(versao.id).catch(() => {})}
        >
          Tentar comparar de novo
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => descartarSpec(versao.id).catch(() => {})}
        >
          Descartar esta revisão
        </Button>
      </div>
    </WidgetFrame>
  );
}

export function StepWidget() {
  const { step } = useConversation();
  if (!step) return null;

  switch (step.id) {
    // Setup / Requisitos
    case "setup.docs_eng":
      return (
        <UploadWidget
          tipo="engenharia"
          hint="Documentos da engenharia (requisição técnica, folha de dados)"
        />
      );
    case "setup.docs_complementares":
      return <ComplementaresWidget />;
    case "setup.docs_forn":
      return (
        <UploadWidget tipo="fornecedor" hint="Proposta do fornecedor" />
      );
    case "setup.extrair":
      return <ExtrairRequisitosWidget />;
    case "requisitos.aprovar":
      return <RequisitosWidget />;

    // Análise
    case "analise.docs_forn":
      return <UploadWidget tipo="fornecedor" hint="Proposta do fornecedor" />;
    case "analise.pronta":
    case "analise.erro":
      return <RetryAnaliseWidget />;
    case "analise.rodando":
      return <ProgressWidget />;
    case "analise.resultado":
      return <AnaliseResultadoWidget />;

    // Ciclo com fornecedor
    case "ciclo.rodada_erro":
      return <RodadaErroWidget />;
    case "ciclo.vinculando":
    case "ciclo.avaliando":
      return <ProgressWidget />;
    case "ciclo.vinculacao_review":
      return step.rodada ? <VinculacaoWidget rodadaId={step.rodada.id} /> : null;
    case "ciclo.decidir":
      return <ItemDecisionWidget />;
    case "ciclo.aguardando_fornecedor":
      return <AguardandoWidget />;

    // Verificação final
    case "verificacao.dispensada":
      return <VerificacaoWidget modo="dispensada" />;
    case "verificacao.aguardando_proposta":
      return <VerificacaoWidget modo="aguardando_proposta" />;
    case "verificacao.rodando":
      return <ProgressWidget />;
    case "verificacao.validar":
      return <VerificacaoWidget modo="validar" />;

    // Fechamento
    case "caso.fechar":
      return <FecharWidget />;
    case "caso.fechado":
      return <ExportWidget />;

    // Revisão de spec (lateral)
    case "spec.comparando":
      return <ProgressWidget />;
    case "spec.diff_decisao":
      return step.specVersao ? (
        <SpecRevisionWidget versao={step.specVersao} />
      ) : null;
    case "spec.erro":
      return <SpecErroWidget />;

    default:
      return null;
  }
}
