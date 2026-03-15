import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const { path: pathSegments } = await params;
    const path = pathSegments.join("/");

    const backendUrl = new URL(`${API_URL}/api/email/${path}`);

    // Copiar search params existentes
    request.nextUrl.searchParams.forEach((value, key) => {
      backendUrl.searchParams.set(key, value);
    });

    // Injetar user_id do Clerk
    backendUrl.searchParams.set("user_id", userId);

    const headers = buildBackendAuthHeaders(userId) as Record<string, string>;
    const contentType = request.headers.get("content-type");
    if (contentType && !contentType.includes("multipart/form-data")) {
      headers["Content-Type"] = contentType;
    }

    const options: RequestInit = {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    };

    const response = await fetch(backendUrl.toString(), options);

    // SSE streaming (chat)
    if (response.headers.get("content-type")?.includes("text/event-stream")) {
      return new NextResponse(response.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    if (!response.ok) {
      const errorText = await response.text();
      try {
        return NextResponse.json(JSON.parse(errorText), {
          status: response.status,
        });
      } catch {
        return NextResponse.json(
          { detail: errorText },
          { status: response.status }
        );
      }
    }

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`Proxy Error [${request.method} /api/email/...]:`, error);
    return NextResponse.json(
      { error: "Erro de comunicação com o backend." },
      { status: 503 }
    );
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
