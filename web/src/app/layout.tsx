import type { Metadata } from "next";
import { Public_Sans } from "next/font/google";

import { Header } from "@/components/header";
import "./globals.css";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Haggle", template: "%s · Haggle" },
  description: "Buy and sell with other students on campus. Your agent haggles; you show up.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${publicSans.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Header />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-6 text-xs text-muted sm:px-6">
            Haggle never handles money. Meet in public spots on campus and pay in person.
          </div>
        </footer>
      </body>
    </html>
  );
}
