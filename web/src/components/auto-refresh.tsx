"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Re-renders the page every few seconds while the backend is still working. */
export function AutoRefresh({ every = 3000 }: { every?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), every);
    return () => clearInterval(id);
  }, [router, every]);
  return null;
}
