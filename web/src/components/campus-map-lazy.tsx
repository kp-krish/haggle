"use client";

import dynamic from "next/dynamic";

/** MapLibre needs the browser (WebGL), so the map renders on the client only. */
export const CampusMap = dynamic(() => import("./campus-map").then((m) => m.CampusMap), {
  ssr: false,
  loading: () => <div className="h-full min-h-[320px] w-full animate-pulse bg-block/40" />,
});
