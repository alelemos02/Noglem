import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { API_URL } from "@/lib/backend";

const ADMIN_EMAILS = [
  "alexandre.nogueira@noglem.com.br",
  "admin@noglem.com.br",
];

async function verifyAdmin() {
  const { userId } = await auth();
  if (!userId) return null;

  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress;
  if (!email || !ADMIN_EMAILS.includes(email)) return null;

  return userId;
}

export async function GET(request: NextRequest) {
  try {
    const userId = await verifyAdmin();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const params = new URLSearchParams();
    if (searchParams.get("category")) params.set("category", searchParams.get("category")!);
    if (searchParams.get("resolved")) params.set("resolved", searchParams.get("resolved")!);

    const url = `${API_URL}/api/admin-notes/${params.toString() ? `?${params}` : ""}`;
    const response = await fetch(url, {
      headers: { "X-API-Key": process.env.INTERNAL_API_KEY! },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
      return NextResponse.json({ error: error.detail }, { status: response.status });
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ error: "Backend indisponível" }, { status: 503 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const userId = await verifyAdmin();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const body = await request.json();

    const response = await fetch(`${API_URL}/api/admin-notes/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.INTERNAL_API_KEY!,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
      return NextResponse.json({ error: error.detail }, { status: response.status });
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ error: "Backend indisponível" }, { status: 503 });
  }
}
