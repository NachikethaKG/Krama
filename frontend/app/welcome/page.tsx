import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { cookies } from "next/headers";
import { LandingPage } from "@/components/landing-page";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.welcome");
  return { title: t("title"), description: t("description") };
}

// Signed-out visitors see this at "/" (the middleware rewrites "/" here); it's also reachable as /welcome.
export default async function WelcomePage() {
  const signedIn = (await cookies()).has("krama_session");
  return <LandingPage signedIn={signedIn} />;
}
