import Link from "next/link";

import { auth } from "@/auth";
import { ListingCard } from "@/components/listing-card";
import { ButtonLink, Empty, INPUT } from "@/components/ui";
import { api } from "@/lib/api";
import { areaLabel, categoryLabel } from "@/lib/format";
import type { BrowseResponse } from "@/lib/types";

const SORTS = [
  { value: "", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];

export default async function Home(props: PageProps<"/">) {
  const session = await auth();
  if (!session?.user) return <Intro />;

  const params = await props.searchParams;
  const pick = (k: string) => (typeof params[k] === "string" ? (params[k] as string) : "");
  const filters = { q: pick("q"), category: pick("category"), area: pick("area"), sort: pick("sort") };
  const data = await api<BrowseResponse>("GET", "/web/listings", { query: filters });
  const filtered = Object.values(filters).some(Boolean);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">On campus now</h1>
          <p className="text-sm text-muted">
            Listed by students, from the website or Discord.
          </p>
        </div>
        <ButtonLink href="/sell">Sell something</ButtonLink>
      </div>

      <form className="grid gap-3 rounded-lg border border-line bg-card p-3 sm:grid-cols-[1fr_auto_auto_auto_auto]">
        <input
          name="q"
          defaultValue={filters.q}
          placeholder="Search: desk lamp, mini fridge…"
          aria-label="Search"
          className={INPUT}
        />
        <select name="category" defaultValue={filters.category} aria-label="Category" className={INPUT}>
          <option value="">All categories</option>
          {data.categories.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        <select name="area" defaultValue={filters.area} aria-label="Area" className={INPUT}>
          <option value="">All areas</option>
          {data.areas
            .filter((a) => a !== "any")
            .map((a) => (
              <option key={a} value={a}>
                {areaLabel(a)}
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
        <button className="rounded-md border border-line px-4 py-2 text-sm font-medium hover:bg-paper">
          Search
        </button>
      </form>

      {data.listings.length ? (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {data.listings.map((listing) => (
            <li key={listing.listing_id}>
              <ListingCard listing={listing} />
            </li>
          ))}
        </ul>
      ) : (
        <Empty>
          {filtered ? (
            <>
              Nothing matches that yet.{" "}
              <Link href="/" className="text-accent underline">
                Clear filters
              </Link>
            </>
          ) : (
            "Nothing listed yet. Be the first."
          )}
        </Empty>
      )}
    </div>
  );
}

function Intro() {
  return (
    <div className="grid gap-10 py-10 md:grid-cols-2 md:items-center">
      <div className="space-y-5">
        <h1 className="text-4xl font-semibold leading-tight tracking-tight">
          Buy and sell with students on campus, without the back-and-forth.
        </h1>
        <p className="text-muted">
          List something in a minute, or say what you&apos;d pay for something you like.
          Your agent negotiates in Discord, keeps your limit to itself, and sets up a pickup
          at a public spot that fits both schedules.
        </p>
        <ButtonLink href="/signin">Sign in with Discord</ButtonLink>
      </div>
      <ol className="space-y-4 rounded-lg border border-line bg-card p-6 text-sm">
        {[
          ["List or browse", "Post a photo and a price, or find something you want."],
          ["Set your limit", "Only your agent ever sees it. The other side never does."],
          ["Watch it haggle", "Every offer shows up in your Discord messages."],
          ["Meet and pay", "Both of you confirm, then meet at a busy public spot."],
        ].map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
              {i + 1}
            </span>
            <span>
              <span className="font-medium">{title}.</span>{" "}
              <span className="text-muted">{body}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
