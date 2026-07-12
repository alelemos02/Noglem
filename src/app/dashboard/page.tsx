import { redirect } from "next/navigation";

// A área logada é PATEC-first: /dashboard é só um alias para bookmarks
export default function DashboardPage() {
  redirect("/dashboard/parecer-tecnico");
}
