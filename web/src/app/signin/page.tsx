import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";
import { Button, Container, PageTitle } from "@/components/ui";
import { DISCORD_INVITE } from "@/lib/links";

export const metadata: Metadata = { title: "Sign in" };

const NOT_MEMBER = "Haggle is for members of the campus Discord server. Join the server, then sign in again.";
const ERRORS: Record<string, string> = { "not-member": NOT_MEMBER, AccessDenied: NOT_MEMBER };

export default async function SignInPage(props: PageProps<"/signin">) {
  if ((await auth())?.user) redirect("/");
  const { error } = await props.searchParams;
  const message = typeof error === "string" ? (ERRORS[error] ?? "Sign-in didn't work. Try again.") : null;

  return (
    <Container narrow>
      <div className="space-y-6 py-10">
        <PageTitle sub="Use the Discord account you use in the campus server. Negotiations and pickup details arrive there as private messages.">
          Sign in to Haggle
        </PageTitle>
        {message && (
          <p role="alert" className="text-sm text-bad">
            {message}
          </p>
        )}
        <form
          action={async () => {
            "use server";
            await signIn("discord", { redirectTo: "/" });
          }}
        >
          <Button>Continue with Discord</Button>
        </form>
        <p className="border-t border-line pt-5 text-sm text-muted">
          Not in the server yet?{" "}
          <a href={DISCORD_INVITE} target="_blank" rel="noreferrer" className="font-semibold text-ink underline underline-offset-4">
            Join Haggle on Discord
          </a>{" "}
          first, then come back and sign in.{" "}
          <Link href="/how" className="underline underline-offset-4 hover:text-ink">
            How it works
          </Link>
        </p>
      </div>
    </Container>
  );
}
