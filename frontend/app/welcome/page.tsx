import { cookies } from "next/headers";
import { LandingPage } from "@/components/landing-page";

export const metadata = {
  title: "Krama · Interactive tutorials recorded from real UI actions",
  description: "Tell Krama what you want to learn; it does the task on the real website, checks every step and turns it into an interactive tutorial.",
};

// Signed-out visitors see this at "/" (the middleware rewrites "/" here); it's also reachable as /welcome.
export default async function WelcomePage() {
  const signedIn = (await cookies()).has("krama_session");
  return <LandingPage signedIn={signedIn} />;
}
