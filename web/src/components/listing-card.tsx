import Image from "next/image";
import Link from "next/link";

import { Price, Trust } from "@/components/ui";
import { areaShort, categoryLabel } from "@/lib/format";
import type { Listing } from "@/lib/types";

export function ListingPhoto({ listing, sizes }: { listing: Listing; sizes: string }) {
  if (!listing.photo) {
    return <div className="flex h-full items-center justify-center text-[13px] text-faint">No photo</div>;
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

/** Photo-first grid item: square photo, title and price on one line, then where and who. */
export function ListingCard({ listing, haggling = 0 }: { listing: Listing; haggling?: number }) {
  return (
    <Link href={`/listings/${listing.listing_id}`} className="group grid gap-2.5">
      <div className="relative aspect-square max-w-full overflow-hidden bg-wash group-hover:outline group-hover:outline-ink">
        <ListingPhoto listing={listing} sizes="(min-width: 1024px) 22vw, (min-width: 640px) 45vw, 100vw" />
        {haggling > 0 && (
          <span className="absolute bottom-2 left-2 bg-paper px-1.5 py-0.5 text-xs">{haggling} haggling</span>
        )}
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[15.5px] font-medium leading-snug">{listing.title ?? "Untitled"}</h3>
        <Price amount={listing.asking} className="text-[15.5px]" />
      </div>
      <p className="-mt-1.5 text-[13px] text-muted">
        {areaShort(listing.area)} · {categoryLabel(listing.category)} ·{" "}
        {listing.mine ? <span className="text-pine">Your listing</span> : <Trust badges={listing.seller_badges} />}
      </p>
    </Link>
  );
}
