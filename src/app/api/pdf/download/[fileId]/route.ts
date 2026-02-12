import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ fileId: string }> }
) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const { fileId } = await params;

    const response = await fetch(`${API_URL}/api/pdf/download/${fileId}`, {
      headers: buildBackendAuthHeaders(userId),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Arquivo não encontrado" },
        { status: 404 }
      );
    }

    const blob = await response.blob();
    return new NextResponse(blob, {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename=converted.docx`,
      },
    });
  } catch (error) {
    console.error("Erro ao baixar arquivo:", error);
    return NextResponse.json(
      { error: "Erro ao baixar arquivo" },
      { status: 503 }
    );
  }
}
