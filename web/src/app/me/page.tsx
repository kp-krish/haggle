import type { Metadata } from "next";
import Link from "next/link";

import { cancelBooking, stopDeal, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { CampusMap } from "@/components/campus-map-lazy";
import { Container, Empty, PageTitle, Price, Section, Status, Trust } from "@/components/ui";
import { api } from "@/lib/api";
import { dealStatus, listingStatus, since } from "@/lib/format";
import type { Deal, Listing, MeResponse, PlacesResponse } from "@/lib/types";

export const metadata: Metadata = { title: "My deals" };

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
  const { stats } = profile;

  return (
    <Container>
      {(working || live.some((d) => LIVE_DEALS.includes(d.state))) && <AutoRefresh every={10000} />}
      <div className="space-y-12">
        <div className="flex flex-wrap items-end justify-between gap-6 border-b border-line pb-5">
          <PageTitle
            sub={
              <>
                <Trust badges={profile.badges} /> · {stats.pickups} completed pickup{stats.pickups === 1 ? "" : "s"}{" "}
                ({stats.as_seller} selling, {stats.as_buyer} buying)
                {stats.no_shows > 0 && ` · ${stats.no_shows} missed`}
                {stats.cancelled > 0 && ` · ${stats.cancelled} cancelled`}
              </>
            }
          >
            My deals
          </PageTitle>
          <Link href="/me/settings" className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline">
            Default times and area
          </Link>
        </div>

        {nextPickup && (
          <section className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <div className="space-y-2">
              <p className="text-[13px] font-semibold text-pine">Next pickup</p>
              <h2 className="text-2xl font-semibold tracking-tight">{nextPickup.title}</h2>
              <p>{nextPickup.pickup}</p>
              {nextPickup.agreed_price !== undefined && <Price amount={nextPickup.agreed_price} className="text-lg" />}
              <p className="text-sm text-muted">Pay in person. A reminder arrives in Discord an hour before.</p>
              <div className="pt-2">
                <CancelBooking deal={nextPickup} />
              </div>
            </div>
            <div className="relative h-64 border border-line">
              <CampusMap areas={places.areas} places={places.places} mode="pickup" spotId={nextPickup.place_id} />
            </div>
          </section>
        )}

        <Section title="In progress">
          {live.length ? <DealList deals={live} /> : <Empty>Nothing in progress. Find something on the browse page.</Empty>}
        </Section>

        <Section
          title="Your listings"
          action={
            <Link href="/sell" className="text-sm font-semibold hover:underline">
              Sell something
            </Link>
          }
        >
          {listings.length ? (
            <ul className="border-t border-line">
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
    <li className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-line py-3">
      <Link href={`/listings/${listing.listing_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
        {listing.title ?? "Untitled listing"}
      </Link>
      <Price amount={listing.asking} />
      <span className="w-40">
        <Status tone={s.tone}>{s.label}</Status>
      </span>
      {listing.status === "open" && (
        <ActionButton action={stopListing.bind(null, listing.listing_id)} variant="quiet">
          Take down
        </ActionButton>
      )}
    </li>
  );
}

function DealList({ deals }: { deals: Deal[] }) {
  return (
    <ul className="border-t border-line">
      {deals.map((d) => {
        const s = dealStatus(d.state, d.pickup, { by: d.cancelled_by, side: d.side });
        return (
          <li key={d.deal_id} className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-line py-3">
            <div className="min-w-0 flex-1">
              <Link href={`/listings/${d.listing_id}`} className="font-medium hover:underline">
                {d.title ?? "Item"}
              </Link>
              <span className="ml-2 text-[13px] text-muted">
                {d.side === "seller" ? "selling" : "buying"} · started {since(d.created_at)}
              </span>
            </div>
            {d.agreed_price !== undefined && <Price amount={d.agreed_price} />}
            <Status tone={s.tone}>{s.label}</Status>
            {LIVE_DEALS.includes(d.state) && (
              <ActionButton action={stopDeal.bind(null, d.deal_id)} variant="quiet">
                Stop
              </ActionButton>
            )}
            {d.state === "confirmed" && <CancelBooking deal={d} />}
          </li>
        );
      })}
    </ul>
  );
}

function CancelBooking({ deal }: { deal: Deal }) {
  const other = deal.side === "seller" ? "buyer" : "seller";
  const after = deal.side === "seller" ? "Your listing comes down." : "The item goes back on sale.";
  return (
    <ActionButton
      action={cancelBooking.bind(null, deal.deal_id)}
      variant="quiet"
      confirm={`Cancel this pickup? The ${other} is told in Discord. ${after}`}
      confirmLabel="Yes, cancel it"
      pendingLabel="Cancelling…"
    >
      Cancel booking
    </ActionButton>
  );
}
