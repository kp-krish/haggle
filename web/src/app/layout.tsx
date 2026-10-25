import type { Metadata } from "next";
import { Schibsted_Grotesk } from "next/font/google";

import { Header } from "@/components/header";
import "./globals.css";

const schibsted = Schibsted_Grotesk({
  variable: "--font-schibsted",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: { default: "Haggle", template: "%s · Haggle" },
  description: "Buy and sell with other students at ASU. Your agent haggles; you meet at a public spot.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Browser extensions add attributes to <html>/<body>; don't treat that as a mismatch.
    <html lang="en" className={`${schibsted.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="flex min-h-full flex-col text-[15px] leading-normal" suppressHydrationWarning>
        <Header />
        <div className="flex-1">{children}</div>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-[1240px] flex-wrap justify-between gap-2 px-4 py-6 text-[13px] text-muted sm:px-6">
            <span>Haggle never handles money. Meet at a public spot and pay in person.</span>
            <span>Map data © OpenStreetMap contributors</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
