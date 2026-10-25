import Image from "next/image";
import Link from "next/link";

import { BadgeList, Price } from "@/components/ui";
import { areaLabel, categoryLabel, since } from "@/lib/format";
import type { Listing } from "@/lib/types";

export function ListingPhoto({ listing, sizes }: { listing: Listing; sizes: string }) {
  if (!listing.photo) {
    return <div className="flex h-full items-center justify-center text-xs text-muted">No photo</div>;
  }
  return (
    <Image
      src={listing.photo}
      alt={listing.title ?? "Item photo"}
      fill
      sizes={sizes}
      className="object-cover"
      // Presigned URLs change on every load, so there's nothing to optimise and cache.
      unoptimized
    />
  );
}

/** A listing in the map's side list: photo, what and where, price on flaps. */
export function ListingRow({ listing }: { listing: Listing }) {
  return (
    <Link
      href={`/listings/${listing.listing_id}`}
      className="group grid grid-cols-[72px_1fr_auto] items-center gap-3 border-b border-line px-4 py-3 hover:bg-paper focus-visible:bg-paper focus-visible:outline-none"
    >
      <div className="relative size-[72px] overflow-hidden border border-line bg-block/40">
        <ListingPhoto listing={listing} sizes="72px" />
      </div>
      <div className="min-w-0 space-y-1">
        <h3 className="truncate font-bold group-hover:underline">{listing.title ?? "Untitled"}</h3>
        <p className="text-xs text-muted">
          {categoryLabel(listing.category)} · {areaLabel(listing.area)} · {since(listing.created_at)}
        </p>
        {listing.mine ? (
          <span className="font-display text-xs font-semibold uppercase tracking-wider text-pin">Your listing</span>
        ) : (
          <BadgeList badges={listing.seller_badges} />
        )}
      </div>
      <Price amount={listing.asking} />
    </Link>
  );
}
