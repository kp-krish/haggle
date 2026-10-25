import Image from "next/image";
import Link from "next/link";

import { auth, signOut } from "@/auth";
import { Flaps } from "@/components/ui";

const NAV = [
  { href: "/", label: "Browse" },
  { href: "/sell", label: "Sell" },
  { href: "/me", label: "My Haggle" },
];

export async function Header() {
  const session = await auth();
  const user = session?.user;

  return (
    <header className="bg-panel text-flap-ink">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="Haggle home">
          <Flaps text="HAGGLE" className="tracking-normal" />
        </Link>
        {user && (
          <nav className="hidden items-center gap-6 font-display text-base font-semibold uppercase tracking-wider text-board-muted sm:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className="hover:text-flap-ink">
                {n.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {user ? (
            <>
              {user.image && (
                <Image src={user.image} alt="" width={28} height={28} className="rounded-full" unoptimized />
              )}
              <span className="hidden md:inline">{user.name}</span>
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/" });
                }}
              >
                <button className="font-display uppercase tracking-wider text-board-muted hover:text-flap-ink">
                  Sign out
                </button>
              </form>
            </>
          ) : (
            <Link href="/signin" className="font-display font-semibold uppercase tracking-wider text-amber hover:underline">
              Sign in
            </Link>
          )}
        </div>
      </div>
      {user && (
        <nav className="flex justify-around border-t border-flap pb-2 pt-1.5 font-display text-sm font-semibold uppercase tracking-wider text-board-muted sm:hidden">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="hover:text-flap-ink">
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
