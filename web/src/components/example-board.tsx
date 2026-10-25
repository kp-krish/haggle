"use client";

import { useEffect, useState } from "react";

import { BoardTable } from "@/components/deal-board";
import type { BoardRow } from "@/lib/types";

/** Example negotiations for the signed-out intro, clearly labelled as examples. */
const SCRIPTS: { title: string; asking: number; steps: [number, number][] }[] = [
  { title: "Mini fridge", asking: 70, steps: [[70, 42], [62, 50], [55, 55]] },
  { title: "Mesh desk chair", asking: 35, steps: [[35, 21], [31, 25], [28, 28]] },
  { title: "Floor lamp", asking: 15, steps: [[15, 9], [13, 11], [12, 12]] },
  { title: "CHM 113 textbooks", asking: 40, steps: [[40, 24], [36, 29], [33, 33]] },
];

function rowsAt(tick: number): BoardRow[] {
  return SCRIPTS.map((s, i) => {
    const step = (tick + i) % s.steps.length;
    const [seller, buyer] = s.steps[step];
    const done = step === s.steps.length - 1;
    return {
      deal_id: `example-${i}`,
      listing_id: "",
      title: s.title,
      asking: s.asking,
      state: done ? "done" : "negotiating",
      rounds: step + 1,
      price: done ? seller : null,
      mine: true,
      seller_offer: seller,
      buyer_offer: buyer,
      updated_at: "",
    };
  });
}

export function ExampleBoard() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setTick((t) => t + 1), 1800);
    return () => clearInterval(id);
  }, []);
  return <BoardTable rows={rowsAt(tick)} />;
}
