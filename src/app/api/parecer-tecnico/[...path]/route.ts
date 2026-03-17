import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

// PATEC backend URL (separate from main backend)
const PATEC_URL = process.env.PATEC_API_URL || "http://localhost:8000";
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || "";

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
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${PATEC_URL}/api/${path}${searchParams ? `?${searchParams}` : ""}`;

    // Build headers - auth + content-type passthrough
    const headers: Record<string, string> = {
      "X-User-Id": userId,
      ...(INTERNAL_API_KEY && { "X-Internal-API-Key": INTERNAL_API_KEY }),
    };

    const contentType = request.headers.get("content-type");
    if (contentType) {
      headers["Content-Type"] = contentType;
    }

    // Read body upfront to avoid "duplex option is required" error when streaming
    let body: BodyInit | undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      if (contentType?.includes("multipart/form-data")) {
        body = await request.arrayBuffer();
      } else {
        body = await request.text();
      }
    }

    const response = await fetch(url, {
      method: request.method,
      headers,
      body,
    });

    // Handle SSE streaming responses
    if (response.headers.get("content-type")?.includes("text/event-stream")) {
      return new NextResponse(response.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    // Handle file downloads (PDF, XLSX, DOCX)
    const respContentType = response.headers.get("content-type") || "";
    if (
      respContentType.includes("application/pdf") ||
      respContentType.includes("application/vnd.openxmlformats") ||
      respContentType.includes("application/octet-stream")
    ) {
      return new NextResponse(response.body, {
        headers: {
          "Content-Type": respContentType,
          "Content-Disposition":
            response.headers.get("Content-Disposition") || "attachment",
        },
      });
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    // Handle errors
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

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`PATEC Proxy Error [${request.method}]:`, error);
    return NextResponse.json(
      { error: "Erro de comunicação com o backend PATEC." },
      { status: 503 }
    );
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
