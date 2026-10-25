import type { Metadata } from "next";

import { BackLink, Container, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

import { PreferencesForm } from "../preferences-form";

export const metadata: Metadata = { title: "Defaults" };

export default async function SettingsPage() {
  const { profile } = await api<MeResponse>("GET", "/web/me");
  return (
    <Container narrow>
      <div className="space-y-7">
        <BackLink href="/me">My deals</BackLink>
        <PageTitle sub="Filled in for you when you sell or make an offer, here and in Discord.">Defaults</PageTitle>
        <PreferencesForm profile={profile} />
      </div>
    </Container>
  );
}
