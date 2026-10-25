"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import type { BoardRow } from "@/lib/types";

const POLL_MS = 6000;

/**
 * One split-flap card holding a whole value ("$65"). The card flips when the value
 * changes, so live numbers still feel like a departure board while staying legible.
 */
function FlapCard({ value, label }: { value: string; label: string }) {
  const previous = useRef(value);
  const [flipping, setFlipping] = useState(false);

  useEffect(() => {
    if (previous.current === value) return;
    previous.current = value;
    setFlipping(true);
    const t = setTimeout(() => setFlipping(false), 260);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <span
      aria-label={`${label} ${value}`}
      className={`flap tabular min-w-[4.5rem] px-2.5 py-1.5 text-center text-lg leading-none ${flipping ? "flip" : ""}`}
    >
      {value}
    </span>
  );
}

function Private() {
  return (
    <span className="inline-flex min-w-[4.5rem] items-center justify-center gap-1.5 rounded-[2px] border border-dashed border-flap px-2 py-1.5 font-sans text-xs text-board-muted">
      <svg aria-hidden viewBox="0 0 16 16" className="size-3" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3" y="7" width="10" height="7" rx="1" />
        <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
      </svg>
      Private
    </span>
  );
}

function money(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : `$${n}`;
}

function statusFor(row: BoardRow): { text: string; tone: "live" | "deal" | "muted" } {
  switch (row.state) {
    case "negotiating":
      return { text: "Haggling", tone: "live" };
    case "scheduling":
    case "confirming":
      return { text: row.mine && row.price ? `Agreed $${row.price}` : "Price agreed", tone: "live" };
    case "confirmed":
    case "done":
      return { text: row.price ? `Sold $${row.price}` : "Sold", tone: "deal" };
    default:
      return { text: "Closed", tone: "muted" };
  }
}

const PILL = {
  live: "bg-amber/15 text-amber ring-amber/40",
  deal: "bg-deal/15 text-deal ring-deal/40",
  muted: "bg-flap text-board-muted ring-flap",
};

/** The live board: starts from the server's rows, then polls for changes. */
export function DealBoard({ initial }: { initial: BoardRow[] }) {
  const [rows, setRows] = useState(initial);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const res = await fetch("/api/board", { cache: "no-store" });
        if (res.ok && !stopped) setRows((await res.json()).rows);
      } catch {
        // Keep showing the last board; the next tick will try again.
      }
    };
    const id = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, []);

  return <BoardTable rows={rows} />;
}

export function BoardTable({ rows }: { rows: BoardRow[] }) {
  if (!rows.length) {
    return (
      <p className="py-6 text-sm text-board-muted">
        No deals on the board yet. It fills up as agents start haggling.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[680px] border-separate border-spacing-y-2">
        <thead>
          <tr className="text-left font-display text-xs uppercase tracking-[0.16em] text-board-muted">
            <th className="w-[38%] font-semibold">Item</th>
            <th className="font-semibold">Asking</th>
            <th className="font-semibold">Seller&apos;s offer</th>
            <th className="font-semibold">Buyer&apos;s offer</th>
            <th className="font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const s = statusFor(row);
            const title = (
              <span className="block truncate font-display text-xl font-semibold uppercase tracking-wide text-flap-ink">
                {row.title}
              </span>
            );
            return (
              <tr key={row.deal_id ?? `${row.listing_id}-${row.updated_at}`} className="align-middle">
                <td className="pr-4">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="min-w-0">
                      {row.listing_id ? (
                        <Link href={`/listings/${row.listing_id}`} className="hover:underline">
                          {title}
                        </Link>
                      ) : (
                        title
                      )}
                      <span className="text-xs text-board-muted">
                        {row.rounds > 0 ? `${row.rounds} round${row.rounds === 1 ? "" : "s"} of offers` : "Just started"}
                      </span>
                    </div>
                    {row.mine && row.listing_id && (
                      <span className="shrink-0 rounded-sm bg-amber px-1.5 py-px font-display text-xs font-semibold uppercase tracking-wider text-panel">
                        You
                      </span>
                    )}
                  </div>
                </td>
                <td><FlapCard value={money(row.asking)} label="Asking" /></td>
                <td>{row.mine ? <FlapCard value={money(row.seller_offer)} label="Seller's offer" /> : <Private />}</td>
                <td>{row.mine ? <FlapCard value={money(row.buyer_offer)} label="Buyer's offer" /> : <Private />}</td>
                <td>
                  <span
                    className={`inline-flex items-center gap-2 rounded-full px-3 py-1 font-display text-base font-semibold uppercase tracking-wider ring-1 ${PILL[s.tone]}`}
                  >
                    <span aria-hidden className="size-2 rounded-full bg-current" />
                    {s.text}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
