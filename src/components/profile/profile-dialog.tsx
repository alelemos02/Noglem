"use client";

/**
 * ProfileDialog — cadastro/edição do perfil Noglem do usuário.
 *
 * O perfil vive no `unsafeMetadata` do Clerk (gravável pelo próprio usuário,
 * legível no frontend e no proxy server-side) — fonte única, sem migration.
 * O apelido é o nome pelo qual a JulIA passa a chamar o usuário.
 */

import { useEffect, useState } from "react";
import { useUser } from "@clerk/nextjs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogBody,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";

export interface NoglemProfile {
  nomeCompleto?: string;
  apelido?: string;
  anoNascimento?: number;
  empresa?: string;
  areaAtuacao?: string;
  onboardingComplete?: boolean;
}

/** Lê o perfil Noglem a partir do unsafeMetadata do Clerk (tolerante a ausência). */
export function readProfile(meta: unknown): NoglemProfile {
  const m = (meta ?? {}) as Record<string, unknown>;
  return {
    nomeCompleto: typeof m.nomeCompleto === "string" ? m.nomeCompleto : undefined,
    apelido: typeof m.apelido === "string" ? m.apelido : undefined,
    anoNascimento:
      typeof m.anoNascimento === "number" ? m.anoNascimento : undefined,
    empresa: typeof m.empresa === "string" ? m.empresa : undefined,
    areaAtuacao: typeof m.areaAtuacao === "string" ? m.areaAtuacao : undefined,
    onboardingComplete: m.onboardingComplete === true,
  };
}

const CURRENT_YEAR = new Date().getFullYear();
const OLDEST_YEAR = 1940;
const YEARS = Array.from(
  { length: CURRENT_YEAR - 16 - OLDEST_YEAR + 1 },
  (_, i) => CURRENT_YEAR - 16 - i
);

export function ProfileDialog({
  open,
  onOpenChange,
  forced = false,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Onboarding obrigatório: não pode fechar sem preencher. */
  forced?: boolean;
}) {
  const { user, isLoaded } = useUser();
  const [nomeCompleto, setNomeCompleto] = useState("");
  const [apelido, setApelido] = useState("");
  const [anoNascimento, setAnoNascimento] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [areaAtuacao, setAreaAtuacao] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !user) return;
    const p = readProfile(user.unsafeMetadata);
    setNomeCompleto(p.nomeCompleto ?? user.fullName ?? "");
    setApelido(p.apelido ?? user.firstName ?? "");
    setAnoNascimento(p.anoNascimento ? String(p.anoNascimento) : "");
    setEmpresa(p.empresa ?? "");
    setAreaAtuacao(p.areaAtuacao ?? "");
  }, [open, user]);

  if (!isLoaded || !user) return null;

  const podeSalvar =
    nomeCompleto.trim() !== "" &&
    apelido.trim() !== "" &&
    anoNascimento !== "" &&
    empresa.trim() !== "" &&
    areaAtuacao.trim() !== "";

  async function salvar() {
    if (!user || !podeSalvar) return;
    setSaving(true);
    try {
      await user.update({
        unsafeMetadata: {
          ...(user.unsafeMetadata ?? {}),
          nomeCompleto: nomeCompleto.trim(),
          apelido: apelido.trim(),
          anoNascimento: Number(anoNascimento),
          empresa: empresa.trim(),
          areaAtuacao: areaAtuacao.trim(),
          onboardingComplete: true,
        },
      });
      toast.success(`Perfil salvo. A JulIA vai te chamar de ${apelido.trim()}.`);
      onOpenChange(false);
    } catch {
      toast.error("Não consegui salvar seu perfil agora. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        // No onboarding obrigatório, ignora tentativas de fechar sem salvar.
        if (forced && !v) return;
        onOpenChange(v);
      }}
    >
      <DialogContent
        className="max-w-lg"
        onEscapeKeyDown={(e) => forced && e.preventDefault()}
        onInteractOutside={(e) => forced && e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{forced ? "Bem-vindo à Noglem" : "Meu perfil"}</DialogTitle>
          <DialogDescription>
            {forced
              ? "Antes de começar, me conta como você quer ser chamado e alguns dados gerais."
              : "Atualize seus dados. A JulIA usa o apelido para falar com você."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <Input
            label="Nome completo"
            value={nomeCompleto}
            onChange={(e) => setNomeCompleto(e.target.value)}
          />
          <Input
            label="Como quer ser chamado"
            hint="É assim que a JulIA vai te chamar no dia a dia."
            value={apelido}
            onChange={(e) => setApelido(e.target.value)}
          />
          <div className="space-y-1.5">
            <label className="text-[13px] font-medium text-fg">
              Ano de nascimento
            </label>
            <Select value={anoNascimento} onValueChange={setAnoNascimento}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione o ano" />
              </SelectTrigger>
              <SelectContent>
                {YEARS.map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Input
            label="Empresa"
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
          />
          <Input
            label="Área de atuação"
            value={areaAtuacao}
            onChange={(e) => setAreaAtuacao(e.target.value)}
          />
        </DialogBody>
        <DialogFooter>
          {!forced && (
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
          )}
          <Button onClick={salvar} loading={saving} disabled={!podeSalvar}>
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
