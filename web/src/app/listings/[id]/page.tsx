import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { discardListing, publishListing, stopListing } from "@/app/actions";
import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { ListingPhoto } from "@/components/listing-card";
import { BadgeList, Pill, PriceTag } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { areaLabel, categoryLabel, dealStatus, listingStatus, since } from "@/lib/format";
import type { Listing, MeResponse } from "@/lib/types";

import { InterestForm } from "./interest-form";

export const metadata: Metadata = { title: "Listing" };

const WORKING = ["processing", "publishing"];

export default async function ListingPage(props: PageProps<"/listings/[id]">) {
  const { id } = await props.params;
  let listing: Listing;
  try {
    listing = await api<Listing>("GET", `/web/listings/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const status = listingStatus(listing.status);
  const working = WORKING.includes(listing.status);

  return (
    <div className="space-y-6">
      {working && <AutoRefresh />}
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back to browsing
      </Link>

      <div className="grid gap-8 md:grid-cols-[3fr_2fr]">
        <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-line bg-card">
          {working && !listing.photo ? (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              Preparing your photo…
            </div>
          ) : (
            <ListingPhoto listing={listing} sizes="(min-width: 768px) 60vw, 100vw" />
          )}
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            {listing.mine && <Pill tone={status.tone}>{status.label}</Pill>}
            <h1 className="text-2xl font-semibold leading-tight">
              {listing.title ?? (working ? "Writing your listing…" : "Untitled")}
            </h1>
            {listing.status !== "processing" && <PriceTag amount={listing.asking} size="lg" />}
            {listing.description && <p className="text-muted">{listing.description}</p>}
            <p className="text-xs text-muted">
              {categoryLabel(listing.category)} · {areaLabel(listing.area)} · listed{" "}
              {since(listing.created_at)}
              {listing.large && " · needs a car or two people"}
            </p>
          </div>

          {listing.mine ? <SellerPanel listing={listing} /> : <BuyerPanel listing={listing} />}
        </div>
      </div>
    </div>
  );
}

function SellerPanel({ listing }: { listing: Listing }) {
  switch (listing.status) {
    case "processing":
      return <Note>Writing the title and description from your photo. This takes a few seconds.</Note>;
    case "publishing":
      return <Note>Publishing to the site and the #listings channel…</Note>;
    case "preview":
      return (
        <div className="space-y-3 rounded-lg border border-line bg-card p-4">
          <p className="text-sm">
            This is how your listing will look. Your lowest price is saved privately; only
            your agent can read it.
          </p>
          <div className="flex gap-2">
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
        <Note tone="bad">
          This item can&apos;t be listed on Haggle
          {listing.rejected_reason ? `: ${listing.rejected_reason}` : "."}
        </Note>
      );
    case "error":
      return <Note tone="bad">Something went wrong writing this listing. Try listing it again.</Note>;
    case "open":
      return (
        <div className="space-y-3 rounded-lg border border-line bg-card p-4">
          <p className="text-sm">
            Live. When a buyer is interested, your agent negotiates in your Discord messages
            and never goes below your lowest price.
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
  const seller = (
    <div className="space-y-2">
      <p className="text-sm font-medium">About the seller</p>
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
        <div className="space-y-2 rounded-lg border border-line bg-card p-4">
          <Pill tone={s.tone}>{s.label}</Pill>
          <p className="text-sm text-muted">
            Follow the negotiation and confirm the deal in your Discord messages.
          </p>
        </div>
        {seller}
      </div>
    );
  }
  if (listing.status !== "open") {
    return <Note>This item is no longer available.</Note>;
  }
  const me = await api<MeResponse>("GET", "/web/me");
  return (
    <div className="space-y-6">
      {seller}
      <div className="space-y-3 rounded-lg border border-line bg-card p-4">
        <h2 className="font-semibold">Interested?</h2>
        {me.profile.paused ? (
          <p className="text-sm text-bad">
            Your account is paused from new deals after repeated missed pickups.
          </p>
        ) : (
          <InterestForm listingId={listing.listing_id} asking={listing.asking} profile={me.profile} />
        )}
      </div>
    </div>
  );
}

function Note({ children, tone }: { children: React.ReactNode; tone?: "bad" }) {
  return (
    <p
      className={`rounded-lg px-4 py-3 text-sm ${tone === "bad" ? "bg-bad-soft text-bad" : "bg-card text-muted border border-line"}`}
    >
      {children}
    </p>
  );
}
