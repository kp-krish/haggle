import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";
import { Button, Container, PageTitle } from "@/components/ui";

export const metadata: Metadata = { title: "Sign in" };

const ERRORS: Record<string, string> = {
  "not-member":
    "Haggle is for members of the campus Discord server. Join the server, then sign in again.",
  AccessDenied:
    "Haggle is for members of the campus Discord server. Join the server, then sign in again.",
};

export default async function SignInPage(props: PageProps<"/signin">) {
  if ((await auth())?.user) redirect("/");
  const { error } = await props.searchParams;
  const message = typeof error === "string" ? (ERRORS[error] ?? "Sign-in didn't work. Try again.") : null;

  return (
    <Container narrow>
    <div className="mx-auto max-w-sm space-y-6 py-8">
      <PageTitle sub="Use the Discord account you use in the campus server. Negotiations and pickup details arrive there as private messages.">
        Sign in
      </PageTitle>
      {message && (
        <p role="alert" className="border-2 border-bad/40 bg-bad-soft px-3 py-2 text-sm text-bad">
          {message}
        </p>
      )}
      <form
        action={async () => {
          "use server";
          await signIn("discord", { redirectTo: "/" });
        }}
      >
        <Button className="w-full">Continue with Discord</Button>
      </form>
    </div>
    </Container>
  );
}
