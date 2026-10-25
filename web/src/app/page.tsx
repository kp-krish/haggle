import Link from "next/link";

import { auth } from "@/auth";
import { CampusMap } from "@/components/campus-map-lazy";
import { DealBoard } from "@/components/deal-board";
import { ExampleBoard } from "@/components/example-board";
import { ListingRow } from "@/components/listing-card";
import { ButtonLink, Empty, INPUT } from "@/components/ui";
import { api } from "@/lib/api";
import { categoryLabel } from "@/lib/format";
import type { BoardRow, BrowseResponse, PlacesResponse } from "@/lib/types";

const SORTS = [
  { value: "", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];
const ZONES = ["north", "central", "south"];

export default async function Home(props: PageProps<"/">) {
  const session = await auth();
  if (!session?.user) return <Intro />;

  const params = await props.searchParams;
  const pick = (k: string) => (typeof params[k] === "string" ? (params[k] as string) : "");
  const filters = { q: pick("q"), category: pick("category"), sort: pick("sort") };
  const area = ZONES.includes(pick("area")) ? pick("area") : "";

  const [browse, board, places] = await Promise.all([
    api<BrowseResponse>("GET", "/web/listings", { query: filters }),
    api<{ rows: BoardRow[] }>("GET", "/web/board"),
    api<PlacesResponse>("GET", "/web/places"),
  ]);

  // Counts per zone for the map; "anywhere" listings show in every zone.
  const counts = Object.fromEntries(
    ZONES.map((z) => [z, browse.listings.filter((l) => l.area === z || l.area === "any").length]),
  );
  const listings = area ? browse.listings.filter((l) => l.area === area || l.area === "any") : browse.listings;
  const filtered = Boolean(area || filters.q || filters.category);
  const zoneHref = (z: string) => {
    const q = new URLSearchParams({ ...filters, ...(z ? { area: z } : {}) });
    for (const [k, v] of [...q.entries()]) if (!v) q.delete(k);
    return q.size ? `/?${q}` : "/";
  };

  return (
    <>
      <section className="bg-panel text-flap-ink">
        <div className="mx-auto max-w-7xl space-y-4 px-4 pt-6 pb-8 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-3xl font-bold uppercase tracking-wide">Live on campus</h1>
              <p className="text-sm text-board-muted">
                Agents haggling right now. Other students&apos; offers stay private; you see your own.
              </p>
            </div>
            <ButtonLink href="/sell" variant="board">
              Sell something
            </ButtonLink>
          </div>
          <DealBoard initial={board.rows} />
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="grid border-2 border-ink bg-card lg:grid-cols-[1.35fr_1fr]">
          <div className="relative h-[380px] border-b-2 border-ink lg:h-[640px] lg:border-r-2 lg:border-b-0">
            <CampusMap areas={places.areas} places={places.places} counts={counts} activeArea={area || undefined} />
            <div className="pointer-events-none absolute bottom-3 left-3 flex gap-3 bg-card/90 px-3 py-1.5 text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="size-2.5 rotate-45 bg-spot" /> Public meeting spot
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="size-2.5 rounded-full bg-pin" /> Items in zone
              </span>
            </div>
          </div>

          <div className="flex min-h-0 flex-col lg:h-[640px]">
            <div className="space-y-3 border-b-2 border-ink p-4">
              <h2 className="font-display text-2xl font-bold uppercase tracking-wide">
                {area ? `For sale · ${area} campus` : "For sale around campus"}
              </h2>
              <nav className="flex flex-wrap gap-1.5" aria-label="Zone">
                {["", ...ZONES].map((z) => (
                  <Link
                    key={z || "all"}
                    href={zoneHref(z)}
                    scroll={false}
                    className={`border-2 px-2.5 py-0.5 font-display text-sm font-semibold uppercase tracking-wider ${
                      area === z ? "border-pin bg-pin text-white" : "border-line text-muted hover:border-ink hover:text-ink"
                    }`}
                  >
                    {z || "All"}
                  </Link>
                ))}
              </nav>
              <form className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_auto_auto]">
                {area && <input type="hidden" name="area" value={area} />}
                <input
                  name="q"
                  defaultValue={filters.q}
                  placeholder="Search: lamp, fridge…"
                  aria-label="Search"
                  className={`${INPUT} col-span-2 sm:col-span-1`}
                />
                <select name="category" defaultValue={filters.category} aria-label="Category" className={INPUT}>
                  <option value="">All categories</option>
                  {browse.categories.map((c) => (
                    <option key={c} value={c}>
                      {categoryLabel(c)}
                    </option>
                  ))}
                </select>
                <select name="sort" defaultValue={filters.sort} aria-label="Sort" className={INPUT}>
                  {SORTS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <button className="col-span-2 border-2 border-ink px-4 py-1.5 font-display font-semibold uppercase tracking-wider hover:bg-paper sm:col-span-3">
                  Search
                </button>
              </form>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {listings.length ? (
                listings.map((l) => <ListingRow key={l.listing_id} listing={l} />)
              ) : (
                <div className="p-4">
                  <Empty>
                    {filtered ? (
                      <>
                        Nothing here yet.{" "}
                        <Link href="/" className="text-pin underline">
                          Show everything
                        </Link>
                      </>
                    ) : (
                      "Nothing listed yet. Be the first."
                    )}
                  </Empty>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}

function Intro() {
  return (
    <>
      <section className="bg-panel text-flap-ink">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_1.3fr] lg:items-center">
          <div className="space-y-5">
            <h1 className="font-display text-5xl font-bold uppercase leading-[0.95] tracking-wide text-balance">
              Your agent haggles. You just show up.
            </h1>
            <p className="max-w-md text-board-muted">
              Buy and sell with other ASU students. Set a secret limit, watch the offers flip in
              your Discord messages, then meet at a busy public spot on campus.
            </p>
            <ButtonLink href="/signin" variant="board">
              Sign in with Discord
            </ButtonLink>
          </div>
          <div className="space-y-2">
            <p className="font-display text-xs uppercase tracking-[0.16em] text-board-muted">Example deals</p>
            <ExampleBoard />
          </div>
        </div>
      </section>
      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-10 sm:px-6 md:grid-cols-3">
        {[
          ["List it or find it", "Post a photo and a price, or pick something you want and set a budget range."],
          ["Your limit stays yours", "Only your agent knows how low or high you'll go. The other side never sees it."],
          ["Meet somewhere public", "Pickups are set at busy campus spots like the Memorial Union or Hayden Library."],
        ].map(([title, body]) => (
          <div key={title} className="space-y-1 border-t-2 border-ink pt-3">
            <h2 className="font-display text-xl font-bold uppercase tracking-wide">{title}</h2>
            <p className="text-sm text-muted">{body}</p>
          </div>
        ))}
      </main>
    </>
  );
}
