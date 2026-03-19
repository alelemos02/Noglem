"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Plus, Copy, Check, Loader2, ShieldAlert } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";

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

  // Consider context: the user mentioned they are the admin. 
  // We should ideally check for a specific email or role.
  const isAdmin = user?.primaryEmailAddress?.emailAddress === "alexandre.nogueira@noglem.com.br" || 
                  user?.primaryEmailAddress?.emailAddress === "admin@noglem.com.br";

  useEffect(() => {
    if (isLoaded && isAdmin) {
      fetchInvites();
    }
  }, [isLoaded, isAdmin]);

  const fetchInvites = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/list`, {
        headers: {
          "X-API-KEY": process.env.NEXT_PUBLIC_INTERNAL_API_KEY || "a1246d7e32ca34a567882f833f13c2c48a22d49d575319b3c20b897883a2b432"
        }
      });
      if (response.ok) {
        const data = await response.json();
        setInvites(data.sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
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
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-KEY": process.env.NEXT_PUBLIC_INTERNAL_API_KEY || "a1246d7e32ca34a567882f833f13c2c48a22d49d575319b3c20b897883a2b432"
        },
        body: JSON.stringify({ expires_at: null })
      });
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
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center space-y-4 text-center">
        <ShieldAlert className="h-16 w-16 text-destructive" />
        <h1 className="text-2xl font-bold">Acesso Negado</h1>
        <p className="text-muted-foreground">Você não tem permissão para acessar esta área.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Convites</h1>
          <p className="text-muted-foreground">Gerencie o acesso exclusivo à plataforma.</p>
        </div>
        <Button onClick={generateInvite} disabled={generating} className="bg-accent hover:bg-accent/90 gap-2">
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Gerar Novo Código
        </Button>
      </div>

      <Card className="border-border">
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
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    Nenhum código gerado ainda.
                  </TableCell>
                </TableRow>
              ) : (
                invites.map((invite) => (
                  <TableRow key={invite.code}>
                    <TableCell className="font-mono font-bold text-lg tracking-wider">
                      {invite.code}
                    </TableCell>
                    <TableCell>
                      {invite.is_used ? (
                        <Badge variant="outline" className="bg-muted text-muted-foreground">Utilizado</Badge>
                      ) : (
                        <Badge variant="success">Disponível</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
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
                          className="hover:bg-accent/10"
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
