import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const formData = await request.formData();

    const response = await fetch(`${API_URL}/api/pdf/extract/download`, {
      method: "POST",
      headers: buildBackendAuthHeaders(userId),
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
      return NextResponse.json(
        { error: error.detail || "Erro ao gerar Excel" },
        { status: response.status }
      );
    }

    const blob = await response.blob();
    return new NextResponse(blob, {
      headers: {
        "Content-Type":
          response.headers.get("content-type") ||
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition":
          response.headers.get("content-disposition") ||
          "attachment; filename=tabelas.xlsx",
      },
    });
  } catch (error) {
    console.error("Erro ao conectar com backend:", error);
    return NextResponse.json(
      { error: "Backend indisponível. Verifique se o servidor está rodando." },
      { status: 503 }
    );
  }
}

