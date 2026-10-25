import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { auth } from "@/auth";
import { ButtonLink, Container, PageTitle } from "@/components/ui";
import { DISCORD_INVITE } from "@/lib/links";

export const metadata: Metadata = { title: "How it works" };

const STEPS: { title: string; body: ReactNode }[] = [
  {
    title: "Join the Haggle Discord server",
    body: (
      <>
        Haggle runs inside our campus Discord server, so you need to be a member before you can sign in. Your agent
        sends offers, pickup plans and reminders there as private messages.{" "}
        <a href={DISCORD_INVITE} className="font-semibold text-ink underline underline-offset-4" target="_blank" rel="noreferrer">
          Join the server
        </a>
        .
      </>
    ),
  },
  {
    title: "Sign in with the same Discord account",
    body: "The website and the bot are the same Haggle. Anything you do on one shows up on the other.",
  },
  {
    title: "List something, or find something",
    body: (
      <>
        To sell, add a photo, an asking price and the lowest price you&apos;d take. To buy, open a listing and give a
        budget range: the low end is where your agent opens, the top is your private max. In Discord the same things
        are <Code>/sell</Code> and <Code>/want</Code>.
      </>
    ),
  },
  {
    title: "Your agent haggles for you",
    body: "The two agents trade offers in your Discord messages. Your lowest price or max never leaves your agent, and it never goes past it. You can change your limit or stop at any point.",
  },
  {
    title: "Confirm the price and the pickup",
    body: "When the agents agree, Haggle picks a time that fits both of your schedules and a busy public spot, like the Memorial Union. Nothing is final until you both press Confirm. Only then do you see who you're meeting.",
  },
  {
    title: "Meet and pay in person",
    body: "You'll get a reminder an hour before. Haggle never handles money. Afterwards, tap Done so the other student's reliability badges count the pickup.",
  },
];

const COMMANDS: [string, string][] = [
  ["/sell", "List an item with a photo and an asking price."],
  ["/want", "Tell your agent what you're looking for. It watches new listings for you."],
  ["/deals", "Your open listings, searches and negotiations."],
  ["/stop", "Take down a listing, stop a search or end a negotiation."],
  ["/cancel", "Cancel a confirmed pickup you can't make."],
];

function Code({ children }: { children: ReactNode }) {
  return <code className="bg-wash px-1 py-px font-mono text-[0.9em] text-ink">{children}</code>;
}

export default async function HowPage() {
  const signedIn = Boolean((await auth())?.user);

  return (
    <Container>
      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-10">
          <PageTitle sub="Buy and sell with other students at ASU. Your agent does the haggling; you just show up.">
            How Haggle works
          </PageTitle>

          <div className="space-y-3 border-l-2 border-pine py-1 pl-5">
            <p className="font-semibold">New here? Join the Discord server first.</p>
            <p className="max-w-prose text-muted">
              Signing in only works for members of the Haggle server, and all the haggling happens there.
            </p>
            <ButtonLink href={DISCORD_INVITE} target="_blank" rel="noreferrer">
              Join Haggle on Discord
            </ButtonLink>
          </div>

          <ol className="border-t border-line">
            {STEPS.map((step, i) => (
              <li key={step.title} className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 border-b border-line py-5">
                <span className="tabular pt-px text-lg font-semibold text-faint">{i + 1}</span>
                <div className="space-y-1">
                  <h2 className="text-lg font-semibold tracking-tight">{step.title}</h2>
                  <p className="max-w-prose text-muted">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold tracking-tight">Can&apos;t make a pickup?</h2>
            <p className="max-w-prose text-muted">
              Cancel it as early as you can, with <Code>/cancel</Code> in Discord or <strong className="font-semibold text-ink">Cancel booking</strong>{" "}
              on{" "}
              <Link href="/me" className="text-ink underline underline-offset-4">
                My deals
              </Link>
              . The other student hears right away. If the buyer cancels, the item goes back on sale; if the seller
              cancels, the listing comes down and the buyer&apos;s agent keeps looking. Cancellations show on your
              profile, and a pickup you skip without cancelling counts as a no-show.
            </p>
          </section>
        </div>

        <aside className="space-y-8 lg:pt-2">
          <section className="space-y-3">
            <h2 className="text-lg font-semibold tracking-tight">Discord commands</h2>
            <dl className="border-t border-line">
              {COMMANDS.map(([name, what]) => (
                <div key={name} className="border-b border-line py-3">
                  <dt>
                    <Code>{name}</Code>
                  </dt>
                  <dd className="mt-1 text-sm text-muted">{what}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="space-y-2 text-sm text-muted">
            <h2 className="text-lg font-semibold tracking-tight text-ink">Good to know</h2>
            <p>Haggle never handles money. Pay in person at the pickup.</p>
            <p>Sellers stay anonymous on listings. Reliability badges come from completed pickups.</p>
            <p>Three missed pickups pause new deals on your account.</p>
          </section>
          {!signedIn && (
            <ButtonLink href="/signin" variant="secondary">
              Already a member? Sign in
            </ButtonLink>
          )}
        </aside>
      </div>
    </Container>
  );
}
