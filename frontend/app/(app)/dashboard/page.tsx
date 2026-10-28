import { redirect } from "next/navigation";

// The home screen shows recent tutorials; "My tutorials" lists them all (#318).
export default function DashboardPage() {
  redirect("/");
}
