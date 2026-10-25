import type { Metadata } from "next";
import Link from "next/link";

import { stopDeal, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { BadgeList, ButtonLink, Empty, Pill, PriceTag, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { dealStatus, listingStatus, money, since } from "@/lib/format";
import type { Deal, Listing, MeResponse } from "@/lib/types";

export const metadata: Metadata = { title: "My Haggle" };

const LIVE_DEALS = ["proposed", "starting", "negotiating", "scheduling", "confirming"];

export default async function MePage() {
  const { profile, listings, deals } = await api<MeResponse>("GET", "/web/me");
  const live = deals.filter((d) => LIVE_DEALS.includes(d.state) || d.state === "confirmed");
  const past = deals.filter((d) => !live.includes(d));
  const working = listings.some((l) => ["processing", "publishing"].includes(l.status));

  return (
    <div className="space-y-10">
      {(working || live.some((d) => LIVE_DEALS.includes(d.state))) && <AutoRefresh every={10000} />}

      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">My Haggle</h1>
          <BadgeList badges={profile.badges} />
          <p className="text-sm text-muted">
            {profile.stats.pickups} completed pickup{profile.stats.pickups === 1 ? "" : "s"} ·{" "}
            {profile.stats.as_seller} as seller · {profile.stats.as_buyer} as buyer
            {profile.stats.no_shows > 0 && ` · ${profile.stats.no_shows} missed`}
          </p>
        </div>
        <Link href="/me/settings" className="text-sm text-muted underline hover:text-ink">
          Default times and area
        </Link>
      </div>

      <Section title="Deals in progress">
        {live.length ? <DealList deals={live} /> : <Empty>No deals in progress.</Empty>}
      </Section>

      <Section title="Your listings" action={<ButtonLink href="/sell" variant="secondary">Sell something</ButtonLink>}>
        {listings.length ? (
          <ul className="divide-y divide-line rounded-lg border border-line bg-card">
            {listings.map((l) => (
              <ListingRow key={l.listing_id} listing={l} />
            ))}
          </ul>
        ) : (
          <Empty>You haven&apos;t listed anything yet.</Empty>
        )}
      </Section>

      {past.length > 0 && (
        <Section title="Past deals">
          <DealList deals={past} />
        </Section>
      )}
    </div>
  );
}

function ListingRow({ listing }: { listing: Listing }) {
  const s = listingStatus(listing.status);
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <Link href={`/listings/${listing.listing_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
        {listing.title ?? "Untitled listing"}
      </Link>
      <span className="tabular text-sm text-muted">{money(listing.asking)}</span>
      <Pill tone={s.tone}>{s.label}</Pill>
      {listing.status === "open" && (
        <ActionButton
          action={stopListing.bind(null, listing.listing_id)}
          variant="danger"
          className="px-3 py-1 text-xs"
        >
          Take down
        </ActionButton>
      )}
    </li>
  );
}

function DealList({ deals }: { deals: Deal[] }) {
  return (
    <ul className="divide-y divide-line rounded-lg border border-line bg-card">
      {deals.map((d) => {
        const s = dealStatus(d.state, d.pickup);
        const stoppable = LIVE_DEALS.includes(d.state);
        return (
          <li key={d.deal_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <Link href={`/listings/${d.listing_id}`} className="block truncate font-medium hover:underline">
                {d.title ?? "Item"}
              </Link>
              <span className="text-xs text-muted">
                You&apos;re the {d.side} · started {since(d.created_at)}
              </span>
            </div>
            {d.agreed_price !== undefined && <PriceTag amount={d.agreed_price} />}
            <Pill tone={s.tone}>{s.label}</Pill>
            {stoppable && (
              <ActionButton
                action={stopDeal.bind(null, d.deal_id)}
                variant="secondary"
                className="px-3 py-1 text-xs"
              >
                Stop
              </ActionButton>
            )}
          </li>
        );
      })}
    </ul>
  );
}
