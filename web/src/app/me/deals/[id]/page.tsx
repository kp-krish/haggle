import type { Metadata } from "next";

import { OfferChart } from "@/components/offer-chart";
import { BackLink, Container, PageTitle, Price } from "@/components/ui";
import { api } from "@/lib/api";
import type { Recap } from "@/lib/types";

export const metadata: Metadata = { title: "Deal recap" };

export default async function RecapPage(props: PageProps<"/me/deals/[id]">) {
  const { id } = await props.params;
  const deal = await api<Recap>("GET", `/web/deals/${id}`);
  const share = deal.asking ? Math.round((deal.saving / deal.asking) * 100) : 0;
  const outcome =
    deal.side === "buyer"
      ? deal.saving > 0
        ? `You saved $${deal.saving} (${share}%) off the asking price.`
        : "You paid the asking price."
      : deal.saving > 0
        ? `You got ${100 - share}% of your asking price.`
        : "You got your full asking price.";
  const gained = deal.reward?.points.reduce((sum, p) => sum + p.points, 0) ?? 0;

  return (
    <Container>
      <div className="space-y-8">
        <BackLink href="/me">My deals</BackLink>
        <PageTitle sub={`${deal.side === "seller" ? "Sold" : "Bought"} after ${deal.rounds} round${deal.rounds === 1 ? "" : "s"}. ${outcome}`}>
          {deal.title ?? "Deal"} recap
        </PageTitle>

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section className="space-y-3">
            <div className="flex items-baseline gap-3">
              <Price amount={deal.agreed_price} className="text-3xl" />
              <span className="tabular text-muted line-through decoration-faint">${deal.asking}</span>
            </div>
            {deal.ladder.length ? (
              <OfferChart ladder={deal.ladder} price={deal.agreed_price} />
            ) : (
              <p className="text-sm text-muted">The round-by-round offers weren&apos;t recorded for this deal.</p>
            )}
          </section>

          <aside className="space-y-6">
            {deal.reward ? (
              <>
                <section className="space-y-2">
                  <h2 className="text-lg font-semibold tracking-tight">
                    <span className="tabular text-pine">+{gained}</span> points
                  </h2>
                  <ul className="border-t border-line text-sm">
                    {deal.reward.points.map((p) => (
                      <li key={p.reason} className="tabular flex justify-between border-b border-line py-2">
                        <span className="text-muted">{p.reason}</span>+{p.points}
                      </li>
                    ))}
                  </ul>
                  {deal.reward.rank && (
                    <p className="text-sm text-muted">
                      {deal.reward.ranked_up ? "Moved up to " : "Rank: "}
                      <strong className="font-semibold text-ink">{deal.reward.rank}</strong>
                    </p>
                  )}
                </section>
                {deal.reward.achievements.length > 0 && (
                  <section className="space-y-2">
                    <h2 className="text-lg font-semibold tracking-tight">Earned</h2>
                    <ul className="space-y-2 text-sm">
                      {deal.reward.achievements.map((a) => (
                        <li key={a.id}>
                          <strong className="block font-semibold">{a.label}</strong>
                          <span className="text-muted">{a.detail}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            ) : (
              <p className="border-t border-line pt-3 text-sm text-muted">
                Points for this deal arrive once the other student confirms the pickup happened.
              </p>
            )}
          </aside>
        </div>
      </div>
    </Container>
  );
}
