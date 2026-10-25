import type { Metadata } from "next";
import Link from "next/link";

import { stopDeal, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { CampusMap } from "@/components/campus-map-lazy";
import { BadgeList, ButtonLink, Container, Empty, PageTitle, Price, Section, Status } from "@/components/ui";
import { api } from "@/lib/api";
import { dealStatus, listingStatus, since } from "@/lib/format";
import type { Deal, Listing, MeResponse, PlacesResponse } from "@/lib/types";

export const metadata: Metadata = { title: "My Haggle" };

const LIVE_DEALS = ["proposed", "starting", "negotiating", "scheduling", "confirming"];

export default async function MePage() {
  const [{ profile, listings, deals }, places] = await Promise.all([
    api<MeResponse>("GET", "/web/me"),
    api<PlacesResponse>("GET", "/web/places"),
  ]);
  const live = deals.filter((d) => LIVE_DEALS.includes(d.state) || d.state === "confirmed");
  const past = deals.filter((d) => !live.includes(d));
  const nextPickup = live.find((d) => d.state === "confirmed" && d.place_id);
  const working = listings.some((l) => ["processing", "publishing"].includes(l.status));

  return (
    <Container>
      {(working || live.some((d) => LIVE_DEALS.includes(d.state))) && <AutoRefresh every={10000} />}
      <div className="space-y-10">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="space-y-2">
            <PageTitle>My Haggle</PageTitle>
            <BadgeList badges={profile.badges} />
            <p className="text-sm text-muted">
              {profile.stats.pickups} completed pickup{profile.stats.pickups === 1 ? "" : "s"} ·{" "}
              {profile.stats.as_seller} as seller · {profile.stats.as_buyer} as buyer
              {profile.stats.no_shows > 0 && ` · ${profile.stats.no_shows} missed`}
            </p>
          </div>
          <Link href="/me/settings" className="font-display text-sm font-semibold uppercase tracking-wider text-muted underline hover:text-ink">
            Default times and area
          </Link>
        </div>

        {nextPickup && (
          <section className="grid border-2 border-ink bg-card md:grid-cols-[1fr_1.4fr]">
            <div className="space-y-2 p-5">
              <p className="font-display text-sm font-semibold uppercase tracking-wider text-spot">Your next pickup</p>
              <h2 className="font-display text-3xl font-bold uppercase leading-none tracking-wide">
                {nextPickup.title}
              </h2>
              <p>{nextPickup.pickup}</p>
              {nextPickup.agreed_price !== undefined && <Price amount={nextPickup.agreed_price} />}
              <p className="text-xs text-muted">Pay in person. A reminder arrives in Discord an hour before.</p>
            </div>
            <div className="relative h-64 border-t-2 border-ink md:h-auto md:border-t-0 md:border-l-2">
              <CampusMap areas={places.areas} places={places.places} mode="pickup" spotId={nextPickup.place_id} />
            </div>
          </section>
        )}

        <Section title="Deals in progress">
          {live.length ? <DealList deals={live} /> : <Empty>No deals in progress.</Empty>}
        </Section>

        <Section title="Your listings" action={<ButtonLink href="/sell" variant="secondary">Sell something</ButtonLink>}>
          {listings.length ? (
            <ul className="border-2 border-ink bg-card">
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
    </Container>
  );
}

function ListingRow({ listing }: { listing: Listing }) {
  const s = listingStatus(listing.status);
  return (
    <li className="flex flex-wrap items-center gap-4 border-b border-line px-4 py-3 last:border-b-0">
      <Link href={`/listings/${listing.listing_id}`} className="min-w-0 flex-1 truncate font-bold hover:underline">
        {listing.title ?? "Untitled listing"}
      </Link>
      <Price amount={listing.asking} size="sm" />
      <Status tone={s.tone}>{s.label}</Status>
      {listing.status === "open" && (
        <ActionButton action={stopListing.bind(null, listing.listing_id)} variant="danger" className="px-3 py-1 text-sm">
          Take down
        </ActionButton>
      )}
    </li>
  );
}

function DealList({ deals }: { deals: Deal[] }) {
  return (
    <ul className="border-2 border-ink bg-card">
      {deals.map((d) => {
        const s = dealStatus(d.state, d.pickup);
        const stoppable = LIVE_DEALS.includes(d.state);
        return (
          <li key={d.deal_id} className="flex flex-wrap items-center gap-4 border-b border-line px-4 py-3 last:border-b-0">
            <div className="min-w-0 flex-1">
              <Link href={`/listings/${d.listing_id}`} className="block truncate font-bold hover:underline">
                {d.title ?? "Item"}
              </Link>
              <span className="text-xs text-muted">
                You&apos;re the {d.side} · started {since(d.created_at)}
              </span>
            </div>
            {d.agreed_price !== undefined && <Price amount={d.agreed_price} size="sm" />}
            <Status tone={s.tone}>{s.label}</Status>
            {stoppable && (
              <ActionButton action={stopDeal.bind(null, d.deal_id)} variant="secondary" className="px-3 py-1 text-sm">
                Stop
              </ActionButton>
            )}
          </li>
        );
      })}
    </ul>
  );
}
