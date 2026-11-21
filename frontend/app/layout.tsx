import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, JetBrains_Mono, Noto_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { AmbientBackground } from "@/components/ui/AmbientBackground";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

const display = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin"],
});

const body = Geist({
  variable: "--font-body",
  subsets: ["latin"],
});

// Hindi and Kannada (#425, #426): real glyphs and bold weights instead of a system fallback with faked bold. Not
// preloaded: the browser fetches them only for a page that shows those scripts (unicode-range).
const devanagari = Noto_Sans_Devanagari({
  variable: "--font-devanagari",
  subsets: ["devanagari"],
  preload: false,
});

const kannada = Noto_Sans_Kannada({
  variable: "--font-kannada",
  subsets: ["kannada"],
  preload: false,
});

const code = JetBrains_Mono({
  variable: "--font-code",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.root");
  return { title: t("title"), description: t("description") };
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#07060f" },
    { media: "(prefers-color-scheme: light)", color: "#f8f5ff" },
  ],
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    // Dark by default; THEME_INIT_SCRIPT switches to the saved light theme before the first paint, so the
    // class and data-theme on <html> can differ from the server's markup on purpose.
    <html
      lang={locale}
      data-theme="dark"
      suppressHydrationWarning
      className={`dark ${display.variable} ${body.variable} ${code.variable} ${devanagari.variable} ${kannada.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="relative min-h-full flex flex-col overflow-x-hidden">
        <AmbientBackground />
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
