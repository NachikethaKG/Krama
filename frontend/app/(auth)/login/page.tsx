import { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata = {
  title: "Sign In · Krama",
  description: "Sign in to access your Krama dashboard and interactive tutorials.",
};

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <div className="size-8 mx-auto border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs text-zinc-500">Loading sign-in…</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
