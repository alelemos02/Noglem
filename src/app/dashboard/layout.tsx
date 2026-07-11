import type { Metadata } from "next";
import { Shell } from "@/components/layout/shell";

// A área logada mantém a marca Jul/IA — `absolute` escapa do template "%s | Noglem"
export const metadata: Metadata = {
  title: { absolute: "Jul/IA — Engineering Intelligence" },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Shell>{children}</Shell>;
}
