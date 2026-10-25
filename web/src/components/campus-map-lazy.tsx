"use client";

import dynamic from "next/dynamic";

/** MapLibre needs the browser (WebGL), so the map renders on the client only. */
export const CampusMap = dynamic(() => import("./campus-map").then((m) => m.CampusMap), {
  ssr: false,
  loading: () => <div className="h-full w-full bg-wash" />,
});
