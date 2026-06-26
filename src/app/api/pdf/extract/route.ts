import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

// Páginas escaneadas viram OCR via Gemini no backend (~40s para um chunk de 4
// páginas em paralelo). 60s é o teto do plano Hobby do Vercel — declarar mais
// que isso invalida a função (foi o que quebrou no passado com maxDuration=300).
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const formData = await request.formData();

    const response = await fetch(`${API_URL}/api/pdf/extract`, {
      method: "POST",
      headers: buildBackendAuthHeaders(userId),
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
      return NextResponse.json(
        { error: error.detail || "Erro na extração" },
        { status: response.status }
      );
    }

    // Verificar se é download Excel (content-type do response)
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("spreadsheetml")) {
      const blob = await response.blob();
      return new NextResponse(blob, {
        headers: {
          "Content-Type": contentType,
          "Content-Disposition": response.headers.get("content-disposition") || "attachment; filename=tables.xlsx",
        },
      });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Erro ao conectar com backend:", error);
    return NextResponse.json(
      { error: "Backend indisponível. Verifique se o servidor está rodando." },
      { status: 503 }
    );
  }
}
