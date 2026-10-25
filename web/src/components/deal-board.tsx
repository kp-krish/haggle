"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import type { BoardRow } from "@/lib/types";

const POLL_MS = 6000;
const ITEM_WIDTH = 16;
const MONEY_WIDTH = 4;
const HIDDEN = "····";

type Cells = { item: string; asking: string; seller: string; buyer: string };

function money(n: number | null | undefined): string {
  return n === null || n === undefined ? "" : `$${n}`;
}

function cellsFor(row: BoardRow): Cells {
  return {
    item: row.title.toUpperCase().slice(0, ITEM_WIDTH),
    asking: money(row.asking),
    // Other students' live offers are private; only your own deals show numbers.
    seller: row.mine ? money(row.seller_offer) : HIDDEN,
    buyer: row.mine ? money(row.buyer_offer) : HIDDEN,
  };
}

function statusFor(row: BoardRow): { text: string; tone: "amber" | "deal" | "muted" } {
  switch (row.state) {
    case "negotiating":
      return { text: `Haggling · round ${Math.max(1, row.rounds)}`, tone: "amber" };
    case "scheduling":
    case "confirming":
      return { text: row.mine && row.price ? `Agreed $${row.price}` : "Price agreed", tone: "amber" };
    case "confirmed":
    case "done":
      return { text: row.price ? `Sold $${row.price}` : "Sold", tone: "deal" };
    default:
      return { text: "Closed", tone: "muted" };
  }
}

/** One fixed-width run of split-flap tiles; tiles flip when their character changes. */
function FlapCell({ value, width, dim = false }: { value: string; width: number; dim?: boolean }) {
  const padded = value.padEnd(width, " ").slice(0, width);
  const previous = useRef(padded);
  const [flipping, setFlipping] = useState<boolean[]>(() => Array(width).fill(false));

  useEffect(() => {
    const changed = [...padded].map((ch, i) => ch !== previous.current[i]);
    previous.current = padded;
    if (!changed.some(Boolean)) return;
    setFlipping(changed);
    const t = setTimeout(() => setFlipping(Array(width).fill(false)), 260);
    return () => clearTimeout(t);
  }, [padded, width]);

  return (
    <span className={`inline-flex gap-[2px] ${dim ? "opacity-55" : ""}`} aria-label={value.trim() || "none"}>
      {[...padded].map((ch, i) => (
        <span key={i} aria-hidden className={`flap px-[3px] py-[3px] text-[15px] ${flipping[i] ? "flip" : ""}`}>
          {ch === " " ? " " : ch}
        </span>
      ))}
    </span>
  );
}

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
      <p className="py-6 font-mono text-sm text-board-muted">
        No deals on the board yet. It fills up as agents start haggling.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-separate border-spacing-y-1.5 font-mono font-semibold">
        <thead>
          <tr className="text-left font-display text-xs uppercase tracking-[0.16em] text-board-muted">
            <th className="font-semibold">Item</th>
            <th className="font-semibold">Asking</th>
            <th className="font-semibold">Seller</th>
            <th className="font-semibold">Buyer</th>
            <th className="font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const c = cellsFor(row);
            const s = statusFor(row);
            return (
              <tr key={row.deal_id ?? `${row.listing_id}-${row.updated_at}`}>
                <td>
                  {row.listing_id ? (
                    <Link href={`/listings/${row.listing_id}`} className="inline-flex items-center gap-2">
                      <FlapCell value={c.item} width={ITEM_WIDTH} />
                      {row.mine && (
                        <span className="rounded-sm bg-amber px-1 font-display text-[11px] uppercase tracking-wider text-panel">
                          You
                        </span>
                      )}
                    </Link>
                  ) : (
                    <FlapCell value={c.item} width={ITEM_WIDTH} />
                  )}
                </td>
                <td><FlapCell value={c.asking} width={MONEY_WIDTH} /></td>
                <td><FlapCell value={c.seller} width={MONEY_WIDTH} dim={!row.mine} /></td>
                <td><FlapCell value={c.buyer} width={MONEY_WIDTH} dim={!row.mine} /></td>
                <td>
                  <span
                    className={`inline-flex items-center gap-2 font-display text-sm uppercase tracking-wider ${
                      s.tone === "deal" ? "text-deal" : s.tone === "amber" ? "text-amber" : "text-board-muted"
                    }`}
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
