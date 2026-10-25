import type { Metadata } from "next";
import Link from "next/link";

import { cancelBooking, stopDeal, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { CampusMap } from "@/components/campus-map-lazy";
import { Container, Empty, PageTitle, Price, Section, Status, Trust } from "@/components/ui";
import { api } from "@/lib/api";
import { dealStatus, listingStatus, since } from "@/lib/format";
import type { Deal, Game, Listing, MeResponse, PlacesResponse } from "@/lib/types";

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

        <RankAndAchievements game={profile.game} />

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
            {(d.has_recap || d.state === "done") && (
              <Link href={`/me/deals/${d.deal_id}`} className="text-sm font-semibold underline-offset-4 hover:underline">
                Recap
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function RankAndAchievements({ game }: { game: Game }) {
  const { rank } = game;
  const earned = game.achievements.filter((a) => a.earned_at);
  return (
    <section className="grid gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
      <div className="space-y-3">
        <p className="text-[13px] font-semibold text-pine">Campus rank</p>
        <h2 className="text-3xl font-semibold tracking-tight">{rank.name}</h2>
        <div className="space-y-1.5">
          <div
            className="h-[3px] w-full bg-line"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(rank.progress * 100)}
            aria-label={rank.next ? `Progress to ${rank.next}` : "Top rank"}
          >
            <div className="h-full bg-pine" style={{ width: `${rank.progress * 100}%` }} />
          </div>
          <p className="tabular text-sm text-muted">
            {rank.points} points
            {rank.next ? ` · ${rank.to_next} to ${rank.next}` : " · top rank"}
          </p>
        </div>
        <ol className="flex flex-wrap gap-x-2 text-[13px] text-faint">
          {game.ranks.map((r, i) => (
            <li key={r.name} className={r.name === rank.name ? "font-semibold text-ink" : ""}>
              {r.name}
              {i < game.ranks.length - 1 && <span className="ml-2 text-faint">→</span>}
            </li>
          ))}
        </ol>
        <p className="text-[13px] text-muted">
          +50 per completed pickup, +10 for closing within 2 rounds, +10 for 20% off as a buyer. Cancelling costs 25,
          a no-show 50. Your rank shows as a role in the Discord server.
        </p>
      </div>

      <div className="space-y-3">
        <p className="text-[13px] font-semibold">
          Achievements <span className="tabular font-normal text-faint">{earned.length} of {game.achievements.length}</span>
        </p>
        <ul className="grid gap-x-8 border-t border-line sm:grid-cols-2">
          {game.achievements.map((a) => (
            <li key={a.id} className="border-b border-line py-2.5">
              <span className={`block text-[15px] font-semibold ${a.earned_at ? "" : "text-faint"}`}>{a.label}</span>
              <span className="block text-[13px] text-muted">
                {a.earned_at
                  ? `Earned ${new Date(a.earned_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`
                  : a.detail}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
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
