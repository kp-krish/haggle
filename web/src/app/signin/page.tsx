import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";
import { Button, Container, PageTitle } from "@/components/ui";

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
      </div>
    </Container>
  );
}
