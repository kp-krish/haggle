import type { Metadata } from "next";

import { api } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

import { SellForm } from "./sell-form";

export const metadata: Metadata = { title: "Sell" };

export default async function SellPage() {
  const me = await api<MeResponse>("GET", "/web/me");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Sell something</h1>
        <p className="text-sm text-muted">
          It also shows up in the #listings channel on Discord.
        </p>
      </div>
      {me.profile.paused ? (
        <p className="rounded-md bg-bad-soft px-4 py-3 text-sm text-bad">
          Your account is paused from new deals after repeated missed pickups.
        </p>
      ) : (
        <SellForm profile={me.profile} />
      )}
    </div>
  );
}
