import { HomeScreen } from "@/components/home/HomeScreen";

export interface HomePageProps {
  searchParams?: Promise<{ prompt?: string | string[] }>;
}

/** `?prompt=` prefills the request ("Plan it fresh" after a failed "Do it for me" run, #402). */
export default async function Page({ searchParams }: HomePageProps) {
  const { prompt } = (await searchParams) ?? {};
  const initialPrompt = typeof prompt === "string" ? prompt.slice(0, 500) : undefined;
  return <HomeScreen initialPrompt={initialPrompt} />;
}
