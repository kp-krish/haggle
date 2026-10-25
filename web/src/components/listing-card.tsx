import Image from "next/image";
import Link from "next/link";

import { BadgeList, PriceTag } from "@/components/ui";
import { areaLabel, categoryLabel, since } from "@/lib/format";
import type { Listing } from "@/lib/types";

export function ListingPhoto({ listing, sizes }: { listing: Listing; sizes: string }) {
  if (!listing.photo) {
    return <div className="flex h-full items-center justify-center text-sm text-muted">No photo</div>;
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

export function ListingCard({ listing }: { listing: Listing }) {
  return (
    <Link
      href={`/listings/${listing.listing_id}`}
      className="group flex flex-col overflow-hidden rounded-lg border border-line bg-card transition-shadow hover:shadow-sm focus-visible:outline-2 focus-visible:outline-accent"
    >
      <div className="relative aspect-[4/3] bg-paper">
        <ListingPhoto listing={listing} sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw" />
        <div className="absolute bottom-2 left-2">
          <PriceTag amount={listing.asking} />
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <h3 className="line-clamp-2 font-medium leading-snug group-hover:underline">
          {listing.title ?? "Untitled"}
        </h3>
        <p className="text-xs text-muted">
          {categoryLabel(listing.category)} · {areaLabel(listing.area)} · {since(listing.created_at)}
        </p>
        <div className="mt-auto pt-1">
          {listing.mine ? (
            <span className="text-xs font-medium text-accent">Your listing</span>
          ) : (
            <BadgeList badges={listing.seller_badges} />
          )}
        </div>
      </div>
    </Link>
  );
}
