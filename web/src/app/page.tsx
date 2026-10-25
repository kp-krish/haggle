import Link from "next/link";

import { auth } from "@/auth";
import { CampusMap } from "@/components/campus-map-lazy";
import { ListingCard } from "@/components/listing-card";
import { NowLine } from "@/components/now-line";
import { ButtonLink, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { categoryLabel } from "@/lib/format";
import { DISCORD_INVITE } from "@/lib/links";
import type { BoardRow, BrowseResponse, Listing, PlacesResponse, ZoneScores } from "@/lib/types";

const ZONES = ["north", "central", "south"];
const SORTS = [
  { value: "", label: "Newest" },
  { value: "price_asc", label: "Price, low to high" },
  { value: "price_desc", label: "Price, high to low" },
];

type Filters = { q: string; category: string; area: string; min: string; max: string; sort: string };

/** A link to the same page with some filters changed (empty values are dropped). */
function href(filters: Filters, change: Partial<Filters>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...filters, ...change })) if (v) q.set(k, v);
  return q.size ? `/?${q}` : "/";
}

const inZone = (l: Listing, zone: string) => !zone || l.area === zone || l.area === "any";

export default async function Home(props: PageProps<"/">) {
  const session = await auth();
  if (!session?.user) return <Intro />;

  const params = await props.searchParams;
  const pick = (k: string) => (typeof params[k] === "string" ? (params[k] as string) : "");
  const filters: Filters = {
    q: pick("q"),
    category: pick("category"),
    area: ZONES.includes(pick("area")) ? pick("area") : "",
    min: pick("min").replace(/\D/g, ""),
    max: pick("max").replace(/\D/g, ""),
    sort: pick("sort"),
  };

  const [browse, board, places, zones] = await Promise.all([
    api<BrowseResponse>("GET", "/web/listings", { query: { q: filters.q, sort: filters.sort } }),
    api<{ rows: BoardRow[] }>("GET", "/web/board"),
    api<PlacesResponse>("GET", "/web/places"),
    api<ZoneScores>("GET", "/web/zones"),
  ]);

  // Search and sort happen on the server; area, category and price narrow here so the
  // filter counts can show what each choice would give.
  const priced = browse.listings.filter(
    (l) => (!filters.min || l.asking >= Number(filters.min)) && (!filters.max || l.asking <= Number(filters.max)),
  );
  const zoneCount = (z: string) => priced.filter((l) => inZone(l, z) && (!filters.category || l.category === filters.category)).length;
  const catCount = (c: string) => priced.filter((l) => inZone(l, filters.area) && (!c || l.category === c)).length;
  const listings = priced.filter((l) => inZone(l, filters.area) && (!filters.category || l.category === filters.category));
  const categories = browse.categories.filter((c) => catCount(c) > 0 || c === filters.category);
  const haggling = (id: string) => board.rows.filter((r) => r.listing_id === id && r.state === "negotiating").length;

  return (
    <div className="mx-auto max-w-[1240px] px-4 sm:px-6">
      <NowLine initial={board.rows} />

      <div className="grid gap-11 pt-8 pb-16 lg:grid-cols-[270px_minmax(0,1fr)]">
        <aside className="grid content-start gap-7 sm:grid-cols-2 lg:sticky lg:top-4 lg:grid-cols-1">
          <div className="sm:col-span-2 lg:col-span-1">
            <h2 className="mb-2 text-[13px] font-semibold">Where</h2>
            <div className="border border-line">
              <div className="relative h-[230px]">
                <CampusMap
                  areas={places.areas}
                  places={places.places}
                  activeArea={filters.area || undefined}
                  query={href(filters, { area: "" }).replace(/^\/\??/, "")}
                  scores={zones.scores}
                />
              </div>
              <p className="border-t border-line px-2.5 py-2 text-[12.5px] text-muted">
                Every pickup is at a busy public spot, marked ◆. Click a zone to narrow the list.
              </p>
            </div>
            <ZoneRivalry zones={zones} />
          </div>

          <FilterList
            title="Area"
            items={[
              { label: "All of campus", href: href(filters, { area: "" }), count: zoneCount(""), on: !filters.area },
              ...ZONES.map((z) => ({
                label: z.charAt(0).toUpperCase() + z.slice(1),
                href: href(filters, { area: z }),
                count: zoneCount(z),
                on: filters.area === z,
              })),
            ]}
          />

          <FilterList
            title="Category"
            items={[
              { label: "Everything", href: href(filters, { category: "" }), count: catCount(""), on: !filters.category },
              ...categories.map((c) => ({
                label: categoryLabel(c),
                href: href(filters, { category: c }),
                count: catCount(c),
                on: filters.category === c,
              })),
            ]}
          />

          <form className="space-y-2">
            <h2 className="text-[13px] font-semibold">Price</h2>
            {Object.entries(filters).map(([k, v]) =>
              v && !["min", "max"].includes(k) ? <input key={k} type="hidden" name={k} value={v} /> : null,
            )}
            <div className="flex items-center gap-2 text-sm text-muted">
              <input name="min" defaultValue={filters.min} placeholder="$0" inputMode="numeric" aria-label="Minimum price" className="w-20 border border-line px-2 py-1.5 text-ink" />
              to
              <input name="max" defaultValue={filters.max} placeholder="Any" inputMode="numeric" aria-label="Maximum price" className="w-20 border border-line px-2 py-1.5 text-ink" />
              <button className="font-semibold text-ink hover:underline">Apply</button>
            </div>
          </form>
        </aside>

        <main>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
            <h1 className="text-3xl font-semibold leading-tight tracking-[-0.025em]">
              {filters.area ? `For sale on ${filters.area} campus` : "For sale around campus"}{" "}
              <span className="font-normal text-faint">
                {listings.length} item{listings.length === 1 ? "" : "s"}
              </span>
            </h1>
            <form className="text-sm text-muted">
              {Object.entries(filters).map(([k, v]) => (v && k !== "sort" ? <input key={k} type="hidden" name={k} value={v} /> : null))}
              <label>
                Sort by{" "}
                <select name="sort" defaultValue={filters.sort} className="border-b border-line bg-transparent py-0.5 text-ink">
                  {SORTS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>{" "}
              <button className="font-semibold text-ink hover:underline">Go</button>
            </form>
          </div>

          <form className="mb-7 flex border-b border-ink">
            {Object.entries(filters).map(([k, v]) => (v && k !== "q" ? <input key={k} type="hidden" name={k} value={v} /> : null))}
            <input
              name="q"
              defaultValue={filters.q}
              placeholder="Search for a mini fridge, a lamp, a textbook…"
              aria-label="Search"
              className="flex-1 bg-transparent py-2.5 text-[17px] placeholder:text-faint focus:outline-none"
            />
            <button className="font-semibold">Search</button>
          </form>

          {listings.length ? (
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-x-6.5 gap-y-8.5">
              {listings.map((l) => (
                <li key={l.listing_id}>
                  <ListingCard listing={l} haggling={haggling(l.listing_id)} />
                </li>
              ))}
            </ul>
          ) : (
            <Empty>
              {Object.values(filters).some(Boolean) ? (
                <>
                  Nothing matches yet.{" "}
                  <Link href="/" className="text-ink underline">
                    Show everything
                  </Link>
                </>
              ) : (
                <>
                  Nothing listed yet.{" "}
                  <Link href="/sell" className="text-ink underline">
                    Sell the first thing
                  </Link>
                </>
              )}
            </Empty>
          )}

          <Promises />
        </main>
      </div>
    </div>
  );
}

/** This week's completed pickups per zone. The map shades zones by the same numbers. */
function ZoneRivalry({ zones }: { zones: ZoneScores }) {
  const total = Object.values(zones.scores).reduce((a, b) => a + b, 0);
  const name = (z: string) => z.charAt(0).toUpperCase() + z.slice(1);
  const ranked = ZONES.map((z) => [z, zones.scores[z] ?? 0] as const).sort((a, b) => b[1] - a[1]);
  return (
    <div className="mt-3 space-y-1">
      <h2 className="text-[13px] font-semibold">Zone rivalry, this week</h2>
      <p className="text-[13.5px] text-muted">
        {total === 0
          ? "No pickups yet this week. The first one puts your zone on top."
          : zones.leader
            ? `${name(zones.leader)} leads with ${zones.scores[zones.leader]} pickup${zones.scores[zones.leader] === 1 ? "" : "s"}.`
            : "It's a tie at the top."}
      </p>
      {total > 0 && (
        <p className="tabular text-[13px] text-faint">{ranked.map(([z, n]) => `${name(z)} ${n}`).join(" · ")}</p>
      )}
    </div>
  );
}

function FilterList({
  title,
  items,
}: {
  title: string;
  items: { label: string; href: string; count: number; on: boolean }[];
}) {
  return (
    <div>
      <h2 className="mb-2 text-[13px] font-semibold">{title}</h2>
      <ul className="grid gap-0.5 text-[14.5px]">
        {items.map((i) => (
          <li key={i.label}>
            <Link
              href={i.href}
              scroll={false}
              aria-current={i.on ? "true" : undefined}
              className={`flex justify-between py-[3px] hover:text-ink ${i.on ? "font-semibold text-ink" : "text-muted"}`}
            >
              {i.label}
              <span className="tabular font-normal text-faint">{i.count}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Promises() {
  return (
    <div className="mt-14 grid gap-6 border-t border-line pt-5 sm:grid-cols-3">
      {[
        ["Your limit stays yours", "Only your agent knows how low or high you'll go. The other side never sees it."],
        ["The haggling happens in Discord", "Watch every offer in your messages and confirm when it's right."],
        ["Pickup is public and planned", "A time that fits both schedules, at a spot like the Memorial Union."],
      ].map(([title, body]) => (
        <p key={title} className="max-w-[34ch] text-sm text-muted">
          <strong className="mb-0.5 block font-semibold text-ink">{title}</strong>
          {body}
        </p>
      ))}
    </div>
  );
}

function Intro() {
  return (
    <main className="mx-auto max-w-[1240px] px-4 sm:px-6">
      <div className="grid gap-10 border-b border-line py-16 lg:grid-cols-[1.1fr_1fr] lg:items-end">
        <h1 className="text-5xl font-semibold leading-[1.05] tracking-[-0.035em] text-balance">
          Buy and sell with students at ASU. Your agent does the haggling.
        </h1>
        <div className="space-y-5">
          <p className="max-w-md text-muted">
            List something in a minute or name your price for something you like. Your agent negotiates in Discord,
            keeps your limit to itself, and sets up a pickup at a busy spot on campus.
          </p>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
            <ButtonLink href="/signin">Sign in with Discord</ButtonLink>
            <a href={DISCORD_INVITE} target="_blank" rel="noreferrer" className="text-sm font-semibold underline underline-offset-4">
              New here? Join the Discord first
            </a>
          </div>
          <Link href="/how" className="block text-sm text-muted underline-offset-4 hover:text-ink hover:underline">
            How Haggle works
          </Link>
        </div>
      </div>
      <div className="pb-16">
        <Promises />
      </div>
    </main>
  );
}
