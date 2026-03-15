import { NextRequest, NextResponse } from "next/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(
      new URL(
        `/dashboard/emails?error=${encodeURIComponent(error)}`,
        request.url
      )
    );
  }

  if (!code || !state) {
    return NextResponse.redirect(
      new URL("/dashboard/emails?error=missing_params", request.url)
    );
  }

  try {
    const headers = buildBackendAuthHeaders(state, true);
    const response = await fetch(
      `${API_URL}/api/email/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
      { method: "POST", headers }
    );

    if (!response.ok) {
      const errorData = await response.text();
      console.error("OAuth callback backend error:", errorData);
      return NextResponse.redirect(
        new URL("/dashboard/emails?error=callback_failed", request.url)
      );
    }

    return NextResponse.redirect(
      new URL("/dashboard/emails?connected=true", request.url)
    );
  } catch (err) {
    console.error("OAuth callback error:", err);
    return NextResponse.redirect(
      new URL("/dashboard/emails?error=callback_failed", request.url)
    );
  }
}
