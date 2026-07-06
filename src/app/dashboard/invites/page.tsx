"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Plus, Copy, Check, ShieldAlert } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { isAdminEmail } from "@/lib/admin";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingBlock } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";

interface InvitationCode {
  code: string;
  is_used: boolean;
  used_by_email: string | null;
  created_at: string;
  expires_at: string | null;
}

export default function AdminInvitesPage() {
  const { user, isLoaded } = useUser();
  const [invites, setInvites] = useState<InvitationCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const isAdmin = isAdminEmail(user?.primaryEmailAddress?.emailAddress);

  useEffect(() => {
    if (isLoaded && isAdmin) {
      fetchInvites();
    }
  }, [isLoaded, isAdmin]);

  const fetchInvites = async () => {
    try {
      const response = await fetch("/api/invites");
      if (response.ok) {
        const data = (await response.json()) as InvitationCode[];
        setInvites(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      }
    } catch (error) {
      console.error("Failed to fetch invites", error);
    } finally {
      setLoading(false);
    }
  };

  const generateInvite = async () => {
    setGenerating(true);
    try {
      const response = await fetch("/api/invites", { method: "POST" });
      if (response.ok) {
        await fetchInvites();
      }
    } catch (error) {
      console.error("Failed to generate invite", error);
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  if (!isLoaded || loading) {
    return <LoadingBlock label="Carregando convites..." />;
  }

  if (!isAdmin) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Acesso negado"
        description="Você não tem permissão para acessar esta área."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Convites"
        description="Gerencie o acesso exclusivo à plataforma."
        actions={
          <Button onClick={generateInvite} loading={generating}>
            {!generating && <Plus className="h-4 w-4" />}
            Gerar novo código
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Códigos Ativos</CardTitle>
          <CardDescription>
            Envie esses códigos para os usuários que você deseja convidar. Cada código é de uso único.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Código</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Criado em</TableHead>
                <TableHead>Utilizado por</TableHead>
                <TableHead className="text-right">Ação</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invites.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-fg-muted">
                    Nenhum código gerado ainda.
                  </TableCell>
                </TableRow>
              ) : (
                invites.map((invite) => (
                  <TableRow key={invite.code}>
                    <TableCell className="font-mono text-base font-medium tracking-wider text-fg">
                      {invite.code}
                    </TableCell>
                    <TableCell>
                      {invite.is_used ? (
                        <Badge variant="secondary">Utilizado</Badge>
                      ) : (
                        <Badge variant="success" dot>Disponível</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-fg-muted">
                      {format(new Date(invite.created_at), "dd/MM/yyyy HH:mm", { locale: ptBR })}
                    </TableCell>
                    <TableCell>
                      {invite.used_by_email || "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {!invite.is_used && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(invite.code)}
                        >
                          {copiedCode === invite.code ? (
                            <Check className="h-4 w-4 text-success" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
