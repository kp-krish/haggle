import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import type { Badge } from "@/lib/types";
import { money } from "@/lib/format";

type Tone = "neutral" | "ok" | "warn" | "bad" | "accent";

const TONES: Record<Tone, string> = {
  neutral: "bg-line/60 text-muted",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  accent: "bg-accent-soft text-accent",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** The price, shaped like a paper tag: the one recurring visual motif. */
export function PriceTag({ amount, size = "md" }: { amount: number; size?: "md" | "lg" }) {
  const big = size === "lg";
  return (
    <span
      className={`tabular relative inline-flex items-center rounded-r-md bg-accent font-semibold text-accent-ink ${
        big ? "py-1.5 pr-3 pl-5 text-xl" : "py-0.5 pr-2 pl-4 text-sm"
      }`}
      style={{ clipPath: "polygon(10px 0, 100% 0, 100% 100%, 10px 100%, 0 50%)" }}
    >
      <span
        aria-hidden
        className={`absolute rounded-full bg-paper ${big ? "left-2 size-1.5" : "left-1.5 size-1"}`}
      />
      {money(amount)}
    </span>
  );
}

export function BadgeList({ badges }: { badges: Badge[] }) {
  if (!badges.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {badges.map((b) => (
        <li key={b.id} title={b.detail}>
          <Pill tone={b.id === "new" ? "neutral" : "ok"}>{b.label}</Pill>
        </li>
      ))}
    </ul>
  );
}

const BUTTON =
  "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
const VARIANTS = {
  primary: "bg-accent text-accent-ink hover:bg-[#9a390c]",
  secondary: "border border-line bg-card text-ink hover:bg-paper",
  danger: "border border-bad/30 bg-card text-bad hover:bg-bad-soft",
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

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export const INPUT =
  "block w-full rounded-md border border-line bg-card px-3 py-2 text-sm placeholder:text-muted/70 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
      {children}
    </p>
  );
}
