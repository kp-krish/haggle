import type { Metadata } from "next";

import { Container, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

import { SellForm } from "./sell-form";

export const metadata: Metadata = { title: "Sell" };

export default async function SellPage() {
  const me = await api<MeResponse>("GET", "/web/me");
  return (
    <Container>
    <div className="space-y-6">
      <PageTitle sub="It shows up on the map and in the #listings channel on Discord.">Sell something</PageTitle>
      {me.profile.paused ? (
        <p className="border-2 border-bad/40 bg-bad-soft px-4 py-3 text-sm text-bad">
          Your account is paused from new deals after repeated missed pickups.
        </p>
      ) : (
        <SellForm profile={me.profile} />
      )}
    </div>
    </Container>
  );
}
