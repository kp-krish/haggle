import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import type { Badge } from "@/lib/types";

export type Tone = "live" | "ok" | "warn" | "bad" | "neutral";

/** Text on split-flap tiles: the board's voice, used for prices and the logo. */
export function Flaps({
  text,
  className = "",
  size = "md",
}: {
  text: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = { sm: "text-sm px-0.5 py-0", md: "text-base px-1 py-0.5", lg: "text-2xl px-1.5 py-1" };
  return (
    <span className={`inline-flex gap-[2px] font-mono font-semibold ${className}`} aria-label={text}>
      {[...text].map((ch, i) => (
        <span key={i} aria-hidden className={`flap ${sizes[size]}`}>
          {ch === " " ? " " : ch}
        </span>
      ))}
    </span>
  );
}

/** A price on a single split-flap card: legible, and still part of the board's voice. */
export function Price({ amount, size = "md" }: { amount: number; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "text-sm px-2 py-0.5", md: "text-lg px-2.5 py-1", lg: "text-3xl px-3.5 py-2" };
  return (
    <span className={`flap tabular font-mono font-semibold leading-none ${sizes[size]}`} aria-label={`$${amount}`}>
      ${amount}
    </span>
  );
}

const LIGHTS: Record<Tone, string> = {
  live: "text-pin",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  neutral: "text-muted",
};

/** A status light: coloured dot plus a short uppercase label. */
export function Status({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-display text-sm font-semibold uppercase tracking-wider ${LIGHTS[tone]}`}
    >
      <span aria-hidden className="size-2 rounded-full bg-current" />
      {children}
    </span>
  );
}

export function BadgeList({ badges }: { badges: Badge[] }) {
  if (!badges.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {badges.map((b) => (
        <li
          key={b.id}
          title={b.detail}
          className={`rounded-sm border px-1.5 py-px font-display text-xs font-semibold uppercase tracking-wider ${
            b.id === "new" ? "border-line text-muted" : "border-ok/40 bg-ok-soft text-ok"
          }`}
        >
          {b.label}
        </li>
      ))}
    </ul>
  );
}

const BUTTON =
  "inline-flex items-center justify-center gap-2 px-4 py-2 font-display text-base font-semibold uppercase tracking-wider transition-colors disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pin";
const VARIANTS = {
  primary: "bg-ink text-card hover:bg-[#2f473b]",
  secondary: "border-2 border-ink bg-card text-ink hover:bg-paper",
  danger: "border-2 border-bad/50 bg-card text-bad hover:bg-bad-soft",
  board: "bg-amber text-panel hover:bg-[#ffc265]",
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
      <span className="block font-display text-sm font-semibold uppercase tracking-wider">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export const INPUT =
  "block w-full border-2 border-line bg-card px-3 py-2 text-sm placeholder:text-muted/70 focus:border-pin focus:outline-none";

export function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-4 border-b-2 border-ink pb-2">
        <h2 className="font-display text-2xl font-bold uppercase tracking-wide">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="border-2 border-dashed border-line px-4 py-8 text-center text-sm text-muted">{children}</p>;
}

export function Container({ children, narrow = false }: { children: ReactNode; narrow?: boolean }) {
  return (
    <main className={`mx-auto w-full px-4 py-8 sm:px-6 ${narrow ? "max-w-2xl" : "max-w-7xl"}`}>{children}</main>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`border-2 border-ink bg-card p-4 ${className}`}>{children}</div>;
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="space-y-1">
      <h1 className="font-display text-4xl font-bold uppercase leading-none tracking-wide">{children}</h1>
      {sub && <p className="text-sm text-muted">{sub}</p>}
    </div>
  );
}
