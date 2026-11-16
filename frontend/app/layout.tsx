import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, JetBrains_Mono } from "next/font/google";
import { AmbientBackground } from "@/components/ui/AmbientBackground";
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
  themeColor: "#07060f",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${display.variable} ${body.variable} ${code.variable} h-full antialiased`}
    >
      <body className="relative min-h-full flex flex-col overflow-x-hidden">
        <AmbientBackground />
        {children}
      </body>
    </html>
  );
}
