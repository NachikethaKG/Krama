import { DashboardView } from "@/components/dashboard";

export const metadata = {
  title: "User Dashboard · Krama",
  description: "View your recorded tutorials, task executions, and workspace runs.",
};

export default function DashboardPage() {
  return <DashboardView />;
}
