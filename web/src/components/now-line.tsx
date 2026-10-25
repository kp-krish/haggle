"use client";

import { useEffect, useRef, useState } from "react";

import type { BoardRow } from "@/lib/types";

const POLL_MS = 6000;
const SHOWN = 4;

function ago(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`;
}

/** One deal as a plain sentence. Other students' offers stay private. */
function sentence(row: BoardRow): string {
  const round = row.rounds > 0 ? `, round ${row.rounds}` : "";
  switch (row.state) {
    case "negotiating":
      if (row.mine) {
        const offer = row.side === "seller" ? row.seller_offer : row.buyer_offer;
        return offer ? `your agent offered $${offer}${round}` : `your agent is haggling${round}`;
      }
      return `being haggled${round}`;
    case "scheduling":
    case "confirming":
      return row.mine && row.price ? `price agreed at $${row.price}` : "price agreed";
    case "confirmed":
    case "done":
      return row.price ? `sold for $${row.price}` : "sold";
    default:
      return "closed";
  }
}

const keyOf = (row?: BoardRow) => (row ? `${row.listing_id}-${row.updated_at}` : null);

export function NowLine({ initial }: { initial: BoardRow[] }) {
  const [rows, setRows] = useState(initial);
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const topKey = useRef(keyOf(initial[0]));

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const res = await fetch("/api/board", { cache: "no-store" });
        if (!res.ok || stopped) return;
        const next: BoardRow[] = (await res.json()).rows;
        const key = keyOf(next[0]);
        if (key && key !== topKey.current) setFreshKey(key);
        topKey.current = key;
        setRows(next);
      } catch {
        // Keep the last line; the next tick will try again.
      }
    };
    const id = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div
      className="grid gap-1 border-b border-line py-3 text-sm sm:grid-cols-[auto_1fr] sm:gap-5"
      aria-live="polite"
    >
      <span className="whitespace-nowrap text-[13px] font-semibold text-pine">Now on campus</span>
      {rows.length ? (
        <div className="flex gap-7 overflow-hidden whitespace-nowrap mask-[linear-gradient(90deg,#000_85%,transparent)]">
          {rows.slice(0, SHOWN).map((row) => {
            const key = keyOf(row)!;
            return (
              <span key={key} className={`inline-flex items-baseline gap-1.5 text-muted ${key === freshKey ? "arrive" : ""}`}>
                <a href={`/listings/${row.listing_id}`} className={`font-medium hover:underline ${row.mine ? "text-pine" : "text-ink"}`}>
                  {row.title}
                </a>
                {sentence(row)}
                <em className="text-[12.5px] not-italic text-faint">{ago(row.updated_at)}</em>
              </span>
            );
          })}
        </div>
      ) : (
        <span className="text-muted">Quiet right now. New deals show up here as agents start haggling.</span>
      )}
    </div>
  );
}
