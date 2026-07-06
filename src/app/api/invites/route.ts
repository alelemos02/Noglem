import { NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import { API_URL } from "@/lib/backend";
import { isAdminEmail } from "@/lib/admin";

// Proxy para os endpoints de convite do backend central.
// A chave interna nunca chega ao browser: o gate é feito aqui, por email de admin.

async function requireAdmin(): Promise<boolean> {
  const user = await currentUser();
  return isAdminEmail(user?.primaryEmailAddress?.emailAddress);
}

function authHeaders(): Record<string, string> {
  const key = process.env.INTERNAL_API_KEY;
  if (!key) {
    throw new Error("INTERNAL_API_KEY não configurada no Next.js");
  }
  return { "X-API-KEY": key };
}

export async function GET() {
  try {
    if (!(await requireAdmin())) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 403 });
    }
    const response = await fetch(`${API_URL}/api/auth/list`, {
      headers: authHeaders(),
      cache: "no-store",
    });
    if (!response.ok) {
      return NextResponse.json(
        { error: "Erro ao listar convites" },
        { status: response.status }
      );
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    console.error("Proxy Error [GET /api/invites]:", error);
    return NextResponse.json(
      { error: "Erro de comunicação com o backend." },
      { status: 503 }
    );
  }
}

export async function POST() {
  try {
    if (!(await requireAdmin())) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 403 });
    }
    const response = await fetch(`${API_URL}/api/auth/generate`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ expires_at: null }),
    });
    if (!response.ok) {
      return NextResponse.json(
        { error: "Erro ao gerar convite" },
        { status: response.status }
      );
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    console.error("Proxy Error [POST /api/invites]:", error);
    return NextResponse.json(
      { error: "Erro de comunicação com o backend." },
      { status: 503 }
    );
  }
}
