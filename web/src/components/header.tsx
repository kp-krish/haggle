import Image from "next/image";
import Link from "next/link";

import { auth, signOut } from "@/auth";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV = [
  { href: "/", label: "Browse" },
  { href: "/sell", label: "Sell" },
  { href: "/me", label: "My deals" },
];
const HOW = { href: "/how", label: "How it works" };

export async function Header() {
  const session = await auth();
  const user = session?.user;

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-[1240px] items-center gap-7 px-4 py-[18px] sm:px-6">
        <Link href="/" className="text-[21px] font-bold tracking-[-0.035em]">
          haggle<span className="text-pine">.</span>
        </Link>
        <nav className="flex gap-5 text-[15px] text-muted">
          {(user ? [...NAV, HOW] : [HOW]).map((n) => (
            <Link key={n.href} href={n.href} className={`hover:text-ink ${n === HOW && user ? "hidden sm:inline" : ""}`}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm text-muted">
          <ThemeToggle />
          {user ? (
            <>
              {user.image && (
                <Image src={user.image} alt="" width={26} height={26} className="rounded-full" unoptimized />
              )}
              <span className="hidden md:inline">{user.name}</span>
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/" });
                }}
              >
                <button className="hover:text-ink">Sign out</button>
              </form>
            </>
          ) : (
            <Link href="/signin" className="font-semibold text-ink hover:underline">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
