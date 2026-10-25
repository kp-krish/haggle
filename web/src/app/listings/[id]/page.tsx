import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { discardListing, publishListing, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { CampusMap } from "@/components/campus-map-lazy";
import { ListingPhoto } from "@/components/listing-card";
import { BackLink, Container, Price, Status, Trust } from "@/components/ui";
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
      <BackLink href="/">All listings</BackLink>

      <div className="mt-5 grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="relative aspect-square max-w-full overflow-hidden bg-wash">
          {working && !listing.photo ? (
            <div className="flex h-full items-center justify-center text-sm text-muted">Preparing your photo…</div>
          ) : (
            <ListingPhoto listing={listing} sizes="(min-width: 1024px) 55vw, 100vw" />
          )}
        </div>

        <div className="space-y-7">
          <div className="space-y-2">
            {listing.mine && <Status tone={status.tone}>{status.label}</Status>}
            <h1 className="text-3xl font-semibold leading-tight tracking-[-0.025em] text-balance">
              {listing.title ?? (working ? "Writing your listing…" : "Untitled")}
            </h1>
            {listing.status !== "processing" && <Price amount={listing.asking} className="text-2xl" />}
          </div>
          {listing.description && <p className="max-w-prose text-muted">{listing.description}</p>}
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 border-t border-line pt-4 text-sm">
            <dt className="text-muted">Where</dt>
            <dd>{areaLabel(listing.area)}</dd>
            <dt className="text-muted">Category</dt>
            <dd>{categoryLabel(listing.category)}</dd>
            <dt className="text-muted">Listed</dt>
            <dd>{since(listing.created_at)}</dd>
            {listing.large && (
              <>
                <dt className="text-muted">Size</dt>
                <dd>Needs a car or two people</dd>
              </>
            )}
            {!listing.mine && (
              <>
                <dt className="text-muted">Seller</dt>
                <dd>
                  <Trust badges={listing.seller_badges} />{" "}
                  <span className="text-muted">· name shared once you both confirm</span>
                </dd>
              </>
            )}
          </dl>
          {listing.mine ? <SellerPanel listing={listing} /> : <BuyerPanel listing={listing} />}
        </div>
      </div>

      <section className="mt-14 grid gap-6 border-t border-line pt-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Where you&apos;d meet</h2>
          <p className="text-sm text-muted">
            One of these public spots, picked once you both agree on a price and a time that fits both schedules.
          </p>
          <ul className="space-y-1 text-[14.5px]">
            {nearby.map((p) => (
              <li key={p.place_id}>
                <span aria-hidden className="mr-2 text-[11px]">◆</span>
                {p.name}
                {p.curbside && <span className="text-muted"> · curbside</span>}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative h-80 border border-line">
          <CampusMap areas={places.areas} places={places.places} activeArea={zone} mode="focus" />
        </div>
      </section>
    </Container>
  );
}

function SellerPanel({ listing }: { listing: Listing }) {
  switch (listing.status) {
    case "processing":
      return <p className="text-sm text-muted">Writing the title and description from your photo. This takes a few seconds.</p>;
    case "publishing":
      return <p className="text-sm text-muted">Publishing to the site and the #listings channel…</p>;
    case "preview":
      return (
        <div className="space-y-3 border-t border-line pt-4">
          <p className="text-sm">
            This is how your listing will look. Your lowest price is saved privately; only your agent can read it.
          </p>
          <div className="flex flex-wrap gap-3">
            <ActionButton action={publishListing.bind(null, listing.listing_id)} pendingLabel="Publishing…">
              Publish
            </ActionButton>
            <ActionButton action={discardListing.bind(null, listing.listing_id)} variant="secondary">
              Discard
            </ActionButton>
          </div>
        </div>
      );
    case "rejected":
      return (
        <p className="text-sm text-bad">
          This item can&apos;t be listed on Haggle{listing.rejected_reason ? `: ${listing.rejected_reason}` : "."}
        </p>
      );
    case "error":
      return <p className="text-sm text-bad">Something went wrong writing this listing. Try listing it again.</p>;
    case "open":
      return (
        <div className="space-y-3 border-t border-line pt-4">
          <p className="text-sm text-muted">
            Live. When someone is interested, your agent negotiates in your Discord messages and never goes below your
            lowest price.
          </p>
          <ActionButton action={stopListing.bind(null, listing.listing_id)} variant="danger">
            Take it down
          </ActionButton>
        </div>
      );
    default:
      return null;
  }
}

async function BuyerPanel({ listing }: { listing: Listing }) {
  if (listing.my_deal) {
    const s = dealStatus(listing.my_deal.state, listing.my_deal.pickup);
    return (
      <div className="space-y-1 border-t border-line pt-4">
        <Status tone={s.tone}>{s.label}</Status>
        <p className="text-sm text-muted">Follow the negotiation and confirm the deal in your Discord messages.</p>
      </div>
    );
  }
  if (listing.status !== "open") return <p className="text-sm text-muted">This item is no longer available.</p>;

  const me = await api<MeResponse>("GET", "/web/me");
  return (
    <div className="space-y-4 border-t border-line pt-5">
      <h2 className="text-lg font-semibold tracking-tight">Make an offer</h2>
      {me.profile.paused ? (
        <p className="text-sm text-bad">Your account is paused from new deals after repeated missed pickups.</p>
      ) : (
        <InterestForm listingId={listing.listing_id} asking={listing.asking} profile={me.profile} />
      )}
    </div>
  );
}
