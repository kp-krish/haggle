import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { discardListing, publishListing, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { CampusMap } from "@/components/campus-map-lazy";
import { ListingPhoto } from "@/components/listing-card";
import { BadgeList, Container, Panel, Price, Status } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { areaLabel, categoryLabel, dealStatus, listingStatus, since } from "@/lib/format";
import type { Listing, MeResponse, PlacesResponse } from "@/lib/types";

import { InterestForm } from "./interest-form";

export const metadata: Metadata = { title: "Listing" };

const WORKING = ["processing", "publishing"];

export default async function ListingPage(props: PageProps<"/listings/[id]">) {
  const { id } = await props.params;
  let listing: Listing;
  let places: PlacesResponse;
  try {
    [listing, places] = await Promise.all([
      api<Listing>("GET", `/web/listings/${id}`),
      api<PlacesResponse>("GET", "/web/places"),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const status = listingStatus(listing.status);
  const working = WORKING.includes(listing.status);
  const zone = places.areas[listing.area] ? listing.area : undefined;
  const nearby = places.places.filter((p) => !zone || p.area === zone);

  return (
    <Container>
      {working && <AutoRefresh />}
      <div className="space-y-6">
        <Link href="/" className="font-display text-sm font-semibold uppercase tracking-wider text-muted hover:text-ink">
          ← Back to the map
        </Link>

        <div className="grid gap-8 lg:grid-cols-[3fr_2fr]">
          <div className="space-y-6">
            <div className="relative aspect-[4/3] max-w-full overflow-hidden border-2 border-ink bg-block/40">
              {working && !listing.photo ? (
                <div className="flex h-full items-center justify-center text-sm text-muted">Preparing your photo…</div>
              ) : (
                <ListingPhoto listing={listing} sizes="(min-width: 1024px) 60vw, 100vw" />
              )}
            </div>
            <div className="space-y-2">
              <h2 className="font-display text-xl font-bold uppercase tracking-wide">
                Where you&apos;d meet
              </h2>
              <div className="relative h-72 border-2 border-ink">
                <CampusMap areas={places.areas} places={places.places} activeArea={zone} mode="focus" />
              </div>
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted">
                {nearby.map((p) => (
                  <li key={p.place_id} className="inline-flex items-center gap-1.5">
                    <span aria-hidden className="size-2 rotate-45 bg-spot" />
                    {p.name}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted">
                The exact spot is picked from these once you both agree, based on both your schedules.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            <div className="space-y-3">
              {listing.mine && <Status tone={status.tone}>{status.label}</Status>}
              <h1 className="font-display text-4xl font-bold uppercase leading-none tracking-wide text-balance">
                {listing.title ?? (working ? "Writing your listing…" : "Untitled")}
              </h1>
              {listing.status !== "processing" && <Price amount={listing.asking} size="lg" />}
              {listing.description && <p className="text-muted">{listing.description}</p>}
              <p className="text-xs text-muted">
                {categoryLabel(listing.category)} · {areaLabel(listing.area)} · listed {since(listing.created_at)}
                {listing.large && " · needs a car or two people"}
              </p>
            </div>
            {listing.mine ? <SellerPanel listing={listing} /> : <BuyerPanel listing={listing} />}
          </div>
        </div>
      </div>
    </Container>
  );
}

function SellerPanel({ listing }: { listing: Listing }) {
  switch (listing.status) {
    case "processing":
      return <Note>Writing the title and description from your photo. This takes a few seconds.</Note>;
    case "publishing":
      return <Note>Publishing to the map and the #listings channel…</Note>;
    case "preview":
      return (
        <Panel className="space-y-3">
          <p className="text-sm">
            This is how your listing will look. Your lowest price is saved privately; only your agent can read it.
          </p>
          <div className="flex flex-wrap gap-2">
            <ActionButton action={publishListing.bind(null, listing.listing_id)} pendingLabel="Publishing…">
              Publish
            </ActionButton>
            <ActionButton action={discardListing.bind(null, listing.listing_id)} variant="secondary">
              Discard
            </ActionButton>
          </div>
        </Panel>
      );
    case "rejected":
      return (
        <Note tone="bad">
          This item can&apos;t be listed on Haggle{listing.rejected_reason ? `: ${listing.rejected_reason}` : "."}
        </Note>
      );
    case "error":
      return <Note tone="bad">Something went wrong writing this listing. Try listing it again.</Note>;
    case "open":
      return (
        <Panel className="space-y-3">
          <p className="text-sm">
            Live. When a buyer is interested, your agent negotiates in your Discord messages and never goes below
            your lowest price.
          </p>
          <ActionButton action={stopListing.bind(null, listing.listing_id)} variant="danger">
            Take it down
          </ActionButton>
        </Panel>
      );
    default:
      return null;
  }
}

async function BuyerPanel({ listing }: { listing: Listing }) {
  const seller = (
    <div className="space-y-2 border-t-2 border-ink pt-3">
      <p className="font-display text-sm font-semibold uppercase tracking-wider">About the seller</p>
      {listing.seller_badges.length ? (
        <BadgeList badges={listing.seller_badges} />
      ) : (
        <p className="text-sm text-muted">No badges yet.</p>
      )}
      <p className="text-xs text-muted">Names are shared only after you both confirm a deal.</p>
    </div>
  );

  if (listing.my_deal) {
    const s = dealStatus(listing.my_deal.state, listing.my_deal.pickup);
    return (
      <div className="space-y-5">
        <Panel className="space-y-2">
          <Status tone={s.tone}>{s.label}</Status>
          <p className="text-sm text-muted">Follow the negotiation and confirm the deal in your Discord messages.</p>
        </Panel>
        {seller}
      </div>
    );
  }
  if (listing.status !== "open") return <Note>This item is no longer available.</Note>;

  const me = await api<MeResponse>("GET", "/web/me");
  return (
    <div className="space-y-6">
      <Panel className="space-y-4">
        <h2 className="font-display text-2xl font-bold uppercase tracking-wide">Make an offer</h2>
        {me.profile.paused ? (
          <p className="text-sm text-bad">Your account is paused from new deals after repeated missed pickups.</p>
        ) : (
          <InterestForm listingId={listing.listing_id} asking={listing.asking} profile={me.profile} />
        )}
      </Panel>
      {seller}
    </div>
  );
}

function Note({ children, tone }: { children: React.ReactNode; tone?: "bad" }) {
  return (
    <p
      className={`border-2 px-4 py-3 text-sm ${
        tone === "bad" ? "border-bad/40 bg-bad-soft text-bad" : "border-line bg-card text-muted"
      }`}
    >
      {children}
    </p>
  );
}
