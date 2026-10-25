import type { Metadata } from "next";
import Link from "next/link";

import { api } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

import { PreferencesForm } from "../preferences-form";

export const metadata: Metadata = { title: "Defaults" };

export default async function SettingsPage() {
  const { profile } = await api<MeResponse>("GET", "/web/me");
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <Link href="/me" className="text-sm text-muted hover:text-ink">
        ← My Haggle
      </Link>
      <div>
        <h1 className="text-2xl font-semibold">Defaults</h1>
        <p className="text-sm text-muted">
          Filled in for you when you sell or make an offer, here and in Discord.
        </p>
      </div>
      <PreferencesForm profile={profile} />
    </div>
  );
}
