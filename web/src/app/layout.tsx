import type { Metadata } from "next";
import { Atkinson_Hyperlegible, Barlow_Condensed, IBM_Plex_Mono } from "next/font/google";

import { Header } from "@/components/header";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible({
  variable: "--font-atkinson",
  subsets: ["latin"],
  weight: ["400", "700"],
});
const barlow = Barlow_Condensed({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["500", "600"],
});

export const metadata: Metadata = {
  title: { default: "Haggle", template: "%s · Haggle" },
  description: "Buy and sell with other students at ASU. Your agent haggles; you meet at a public spot.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Browser extensions add attributes to <html>/<body>; don't treat that as a mismatch.
    <html
      lang="en"
      className={`${atkinson.variable} ${barlow.variable} ${plexMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col" suppressHydrationWarning>
        <Header />
        <div className="flex-1">{children}</div>
        <footer className="border-t-2 border-ink">
          <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-2 px-4 py-5 text-xs text-muted sm:px-6">
            <span>Haggle never handles money. Meet at a public spot and pay in person.</span>
            <span>Map data © OpenStreetMap contributors</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
