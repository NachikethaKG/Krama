import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, JetBrains_Mono } from "next/font/google";
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

const code = JetBrains_Mono({
  variable: "--font-code",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Krama",
  description: "Verified, interactive software tutorials",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#07060f" },
    { media: "(prefers-color-scheme: light)", color: "#f8f5ff" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Dark by default; THEME_INIT_SCRIPT switches to the saved light theme before the first paint, so the
    // class and data-theme on <html> can differ from the server's markup on purpose.
    <html
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
      className={`dark ${display.variable} ${body.variable} ${code.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="relative min-h-full flex flex-col overflow-x-hidden">
        <AmbientBackground />
        {children}
      </body>
    </html>
  );
}
