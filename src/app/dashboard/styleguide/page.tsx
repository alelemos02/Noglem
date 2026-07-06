"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { FileSearch, ShieldAlert, Table as TableIcon } from "lucide-react";
import { isAdminEmail } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { Dropzone } from "@/components/ui/dropzone";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner, LoadingBlock } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const swatches = [
  { name: "canvas", cls: "bg-canvas" },
  { name: "surface-1", cls: "bg-surface-1" },
  { name: "surface-2", cls: "bg-surface-2" },
  { name: "surface-3", cls: "bg-surface-3" },
  { name: "accent", cls: "bg-accent" },
  { name: "success", cls: "bg-success" },
  { name: "warning", cls: "bg-warning" },
  { name: "danger", cls: "bg-danger" },
  { name: "info", cls: "bg-info" },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="microlabel">{title}</h2>
      {children}
    </section>
  );
}

export default function StyleguidePage() {
  const { user, isLoaded } = useUser();
  const confirm = useConfirm();
  const [progressDemo] = useState(66);

  if (!isLoaded) return <LoadingBlock />;

  if (!isAdminEmail(user?.primaryEmailAddress?.emailAddress)) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Acesso restrito"
        description="Esta página é interna, disponível apenas para administradores."
      />
    );
  }

  return (
    <div className="space-y-12">
      <PageHeader
        title="Styleguide"
        description="Referência viva do design system JulIA v3 — instrumento de precisão. Página interna."
      />

      <Section title="Paleta">
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-9">
          {swatches.map((s) => (
            <div key={s.name}>
              <div className={`h-11 rounded-md border border-edge ${s.cls}`} />
              <p className="mt-1.5 font-mono text-[10px] text-fg-subtle">{s.name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Tipografia">
        <div className="space-y-3 rounded-lg border border-edge bg-surface-1 p-5">
          <p className="text-xl font-semibold tracking-tight">
            IBM Plex Sans — títulos e interface
          </p>
          <p className="text-sm text-fg-muted">
            Corpo de texto em Plex Sans regular. Compare documentação de projeto
            com propostas de fornecedores, item a item.
          </p>
          <p className="font-mono text-[13px] tabular-nums">
            IBM Plex Mono — TIT-1201A · 4–20 mA · HART 7 · 0–250 °C
          </p>
          <p className="microlabel">Microlabel — instrumentação · 03 ferramentas</p>
        </div>
      </Section>

      <Section title="Botões">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primário</Button>
          <Button variant="secondary">Secundário</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Destrutivo</Button>
          <Button variant="link">Link</Button>
          <Button loading>Processando</Button>
          <Button disabled>Desabilitado</Button>
          <Button size="sm" variant="secondary">Pequeno</Button>
        </div>
      </Section>

      <Section title="Badges">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="success" dot>Live</Badge>
          <Badge variant="info">Beta</Badge>
          <Badge variant="secondary">Em breve</Badge>
          <Badge variant="success">A · Conforme</Badge>
          <Badge variant="warning">B · Ressalva</Badge>
          <Badge variant="error">C · Não conforme</Badge>
          <Badge variant="default">Accent</Badge>
          <Badge variant="outline">Outline</Badge>
        </div>
      </Section>

      <Section title="Feedback — toast e confirmação">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            onClick={() =>
              toast.success("Excel gerado", {
                description: "8 tabelas exportadas de 12 páginas.",
              })
            }
          >
            Toast de sucesso
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.error("Falha ao processar a página 7", {
                description: "As demais páginas foram extraídas normalmente.",
              })
            }
          >
            Toast de erro
          </Button>
          <Button
            variant="secondary"
            onClick={async () => {
              const ok = await confirm({
                title: "Excluir coleção?",
                description:
                  "“Manuais de Engenharia” e seus 24 documentos serão removidos permanentemente.",
                confirmLabel: "Excluir coleção",
                variant: "danger",
              });
              toast.info(ok ? "Confirmado" : "Cancelado");
            }}
          >
            Confirmação destrutiva
          </Button>
        </div>
      </Section>

      <Section title="Alertas inline">
        <div className="max-w-xl space-y-3">
          <Alert variant="info">
            Arquivos acima de 4 MB são divididos automaticamente antes do envio.
          </Alert>
          <Alert variant="warning" title="Processamento parcial">
            3 páginas não puderam ser processadas — o Excel contém as demais.
          </Alert>
          <Alert variant="danger">Falha na conexão com o serviço. Tente novamente.</Alert>
          <Alert variant="success">Análise concluída sem pendências.</Alert>
        </div>
      </Section>

      <Section title="Formulário">
        <div className="grid max-w-xl gap-4">
          <Input label="Nome do parecer" placeholder="PAR-2024-018" hint="Identificador do pacote" />
          <Textarea label="Observações" placeholder="Notas da análise..." rows={3} />
          <Select defaultValue="pt">
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Idioma" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pt">Português</SelectItem>
              <SelectItem value="en">Inglês</SelectItem>
              <SelectItem value="es">Espanhol</SelectItem>
            </SelectContent>
          </Select>
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            <Checkbox defaultChecked /> Melhorar texto após tradução
          </label>
        </div>
      </Section>

      <Section title="Progresso e loading">
        <div className="max-w-xl space-y-5">
          <Progress value={progressDemo} label="Processando parte 2 de 3 — OCR em andamento" />
          <Progress indeterminate label="Analisando documento" />
          <div className="flex items-center gap-4 text-fg-muted">
            <Spinner size="xs" /> <Spinner size="sm" /> <Spinner size="md" />
            <Spinner size="lg" className="text-accent" />
          </div>
        </div>
      </Section>

      <Section title="Dropzone">
        <div className="max-w-xl">
          <Dropzone
            onFiles={(files) => toast.info(`${files.length} arquivo(s) recebido(s)`)}
            accept=".pdf"
            maxSizeMB={50}
            hint="Até 50 MB — arquivos acima de 4 MB são divididos automaticamente"
          />
        </div>
      </Section>

      <Section title="Tabs e tabela densa">
        <Tabs defaultValue="instrumentos">
          <TabsList>
            <TabsTrigger value="instrumentos">
              Instrumentos <span className="font-mono text-xs tabular-nums text-fg-subtle">142</span>
            </TabsTrigger>
            <TabsTrigger value="loops">
              Loops <span className="font-mono text-xs tabular-nums text-fg-subtle">38</span>
            </TabsTrigger>
          </TabsList>
          <TabsContent value="instrumentos">
            <Card className="gap-0 overflow-hidden py-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tag</TableHead>
                    <TableHead>Descrição</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Faixa</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-mono text-xs">TIT-1201A</TableCell>
                    <TableCell>Transmissor de temperatura</TableCell>
                    <TableCell>RTD Pt-100</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">0–250 °C</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono text-xs">PIT-1305</TableCell>
                    <TableCell>Transmissor de pressão manométrica</TableCell>
                    <TableCell>Piezoresistivo</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">0–16 bar g</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono text-xs">FIT-2101</TableCell>
                    <TableCell>Medidor de vazão mássica</TableCell>
                    <TableCell>Coriolis</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">0–12 000 kg/h</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Card>
          </TabsContent>
          <TabsContent value="loops">
            <EmptyState
              icon={TableIcon}
              title="Nenhum loop identificado"
              description="Verifique se o P&ID é vetorial — arquivos raster não são suportados."
              size="sm"
            />
          </TabsContent>
        </Tabs>
      </Section>

      <Section title="Empty state e cards">
        <div className="grid gap-4 md:grid-cols-2">
          <EmptyState
            icon={FileSearch}
            title="Nenhuma coleção ainda"
            description="Crie sua primeira coleção para conversar com seus documentos."
            action={<Button size="sm">Criar coleção</Button>}
          />
          <Card interactive className="gap-2 py-5">
            <CardHeader>
              <CardTitle className="text-sm">Extrator de Tabelas</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[13px] text-fg-muted">
                Card interativo — hover muda borda e superfície, sem translate.
              </p>
            </CardContent>
          </Card>
        </div>
      </Section>
    </div>
  );
}
