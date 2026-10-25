"use client";

import { useState } from "react";

import type { LadderStep } from "@/lib/types";

const W = 640;
const H = 250;
const M = { top: 16, right: 64, bottom: 32, left: 46 };
const SIDES = [
  { side: "seller", label: "Seller", color: "var(--color-seller)" },
  { side: "buyer", label: "Buyer", color: "var(--color-buyer)" },
] as const;

function ticks(lo: number, hi: number): number[] {
  const raw = (hi - lo) / 4;
  const mag = 10 ** Math.floor(Math.log10(Math.max(raw, 1)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

/**
 * The negotiation as two lines closing in on the final price: the seller's offers
 * coming down, the buyer's going up. Hover a round to read its offers.
 */
export function OfferChart({ ladder, price }: { ladder: LadderStep[]; price: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const rounds = Math.max(1, ...ladder.map((s) => s.round));
  const amounts = [...ladder.map((s) => s.amount), price];
  const pad = Math.max(2, (Math.max(...amounts) - Math.min(...amounts)) * 0.12);
  const lo = Math.max(0, Math.min(...amounts) - pad);
  const hi = Math.max(...amounts) + pad;

  const x = (round: number) =>
    rounds === 1 ? M.left + (W - M.left - M.right) / 2 : M.left + ((round - 1) / (rounds - 1)) * (W - M.left - M.right);
  const y = (amount: number) => M.top + (1 - (amount - lo) / (hi - lo)) * (H - M.top - M.bottom);
  const series = SIDES.map((s) => ({ ...s, steps: ladder.filter((l) => l.side === s.side) }));
  const at = (round: number) => series.map((s) => ({ ...s, step: s.steps.find((l) => l.round === round) }));
  const colWidth = (W - M.left - M.right) / Math.max(rounds - 1, 1);

  return (
    <figure className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-3 text-[13px]">
        <div className="flex gap-4" aria-hidden>
          {SIDES.map((s) => (
            <span key={s.side} className="inline-flex items-center gap-1.5 text-muted">
              <span className="inline-block h-0.5 w-4 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-muted">
            <span className="inline-block w-4 border-t border-dashed border-faint" />
            Final price
          </span>
        </div>
        <p className="tabular text-muted" aria-live="polite">
          {hover === null
            ? "Hover a round to see its offers"
            : `Round ${hover}: ` +
              at(hover)
                .map((s) => (s.step ? `${s.label.toLowerCase()} $${s.step.amount}${s.step.accept ? " (accepted)" : ""}` : null))
                .filter(Boolean)
                .join(", ")}
        </p>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full"
        role="img"
        aria-label={`Offers over ${rounds} rounds, ending at $${price}`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks(lo, hi).map((v) => (
          <g key={v}>
            <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--color-line)" strokeWidth={1} />
            <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end" fontSize={12} fill="var(--color-muted)" className="tabular">
              ${v}
            </text>
          </g>
        ))}
        {Array.from({ length: rounds }, (_, i) => i + 1).map((r) => (
          <text key={r} x={x(r)} y={H - 10} textAnchor="middle" fontSize={12} fill="var(--color-muted)">
            {rounds <= 12 || r % 2 === 1 ? `Round ${r}` : ""}
          </text>
        ))}

        <line
          x1={M.left}
          x2={W - M.right}
          y1={y(price)}
          y2={y(price)}
          stroke="var(--color-faint)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />

        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} stroke="var(--color-faint)" strokeWidth={1} />}

        {series.map((s) => (
          <g key={s.side}>
            <polyline
              points={s.steps.map((l) => `${x(l.round)},${y(l.amount)}`).join(" ")}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {s.steps.map((l) => (
              <circle
                key={l.round}
                cx={x(l.round)}
                cy={y(l.amount)}
                r={l.accept || hover === l.round ? 5 : 4}
                fill={l.accept ? "var(--color-paper)" : s.color}
                stroke={l.accept ? s.color : "var(--color-paper)"}
                strokeWidth={2}
              />
            ))}
            {/* Direct label at the opening offer; the end of the lines carries the price. */}
            {s.steps.length > 0 && (
              <text
                x={x(s.steps[0].round) + 8}
                y={y(s.steps[0].amount)}
                dy={s.side === "seller" ? "-0.9em" : "1.5em"}
                fontSize={12}
                fill="var(--color-ink)"
              >
                {s.label} opens at ${s.steps[0].amount}
              </text>
            )}
          </g>
        ))}

        <text x={W - M.right + 10} y={y(price)} dy="0.32em" fontSize={12} fontWeight={600} fill="var(--color-ink)" className="tabular">
          ${price}
        </text>

        {/* Hover targets: one full-height column per round, wider than the marks. */}
        {Array.from({ length: rounds }, (_, i) => i + 1).map((r) => (
          <rect
            key={r}
            x={x(r) - colWidth / 2}
            y={M.top}
            width={rounds === 1 ? W - M.left - M.right : colWidth}
            height={H - M.top - M.bottom}
            fill="transparent"
            onMouseEnter={() => setHover(r)}
            onFocus={() => setHover(r)}
            tabIndex={0}
            aria-label={`Round ${r}`}
          />
        ))}
      </svg>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink">Show as a table</summary>
        <table className="tabular mt-2 w-full max-w-sm text-left">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="py-1.5 font-normal">Round</th>
              <th className="py-1.5 font-normal">Seller</th>
              <th className="py-1.5 font-normal">Buyer</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rounds }, (_, i) => i + 1).map((r) => (
              <tr key={r} className="border-b border-line">
                <td className="py-1.5">{r}</td>
                {at(r).map((s) => (
                  <td key={s.side} className="py-1.5">
                    {s.step ? `$${s.step.amount}${s.step.accept ? " accepted" : ""}` : "–"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
