import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import type { Badge } from "@/lib/types";

export type Tone = "live" | "ok" | "warn" | "bad" | "neutral";

const TONES: Record<Tone, string> = {
  live: "text-pine",
  ok: "text-pine",
  warn: "text-warn",
  bad: "text-bad",
  neutral: "text-muted",
};

/** State as plain coloured text: no chips, no dots. */
export function Status({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`text-sm ${TONES[tone]}`}>{children}</span>;
}

export function Price({ amount, className = "" }: { amount: number; className?: string }) {
  return <span className={`tabular font-semibold ${className}`}>${amount}</span>;
}

/** Seller reliability as a few words, e.g. "Reliable seller · Trusted". "New" stays quiet. */
export function Trust({ badges }: { badges: Badge[] }) {
  const earned = badges.filter((b) => b.id !== "new");
  if (!earned.length) return <span className="text-muted">New seller</span>;
  return (
    <span className="text-pine" title={earned.map((b) => b.detail).join("; ")}>
      {earned.map((b) => b.label).join(" · ")}
    </span>
  );
}

const BUTTON =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-[15px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine";
const VARIANTS = {
  primary: "bg-ink text-paper hover:opacity-85",
  secondary: "border border-ink bg-paper text-ink hover:bg-wash",
  danger: "border border-bad/40 bg-paper text-bad hover:bg-bad/5",
  quiet: "px-0 py-0 text-muted underline-offset-4 hover:text-ink hover:underline",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof VARIANTS }) {
  return <button className={`${BUTTON} ${VARIANTS[variant]} ${className}`} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: keyof typeof VARIANTS }) {
  return <Link className={`${BUTTON} ${VARIANTS[variant]} ${className}`} {...props} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="block text-[13px] text-muted">{hint}</span>}
    </label>
  );
}

export const INPUT =
  "block w-full border border-line bg-paper px-3 py-2 text-[15px] placeholder:text-faint focus:border-ink focus:outline-none";

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="border-t border-line py-8 text-sm text-muted">{children}</p>;
}

export function Container({ children, narrow = false }: { children: ReactNode; narrow?: boolean }) {
  return (
    <main className={`mx-auto w-full px-4 pt-8 pb-16 sm:px-6 ${narrow ? "max-w-xl" : "max-w-[1240px]"}`}>
      {children}
    </main>
  );
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="space-y-1">
      <h1 className="text-3xl font-semibold leading-tight tracking-[-0.025em] text-balance">{children}</h1>
      {sub && <p className="text-[15px] text-muted">{sub}</p>}
    </div>
  );
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="text-sm text-muted hover:text-ink">
      ← {children}
    </Link>
  );
}
