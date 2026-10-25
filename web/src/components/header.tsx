import Image from "next/image";
import Link from "next/link";

import { auth, signOut } from "@/auth";

export async function Header() {
  const session = await auth();
  const user = session?.user;

  return (
    <header className="border-b border-line bg-card">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="text-lg font-bold tracking-tight">
          haggle
        </Link>
        {user && (
          <nav className="flex items-center gap-5 text-sm text-muted">
            <Link href="/" className="hover:text-ink">
              Browse
            </Link>
            <Link href="/sell" className="hover:text-ink">
              Sell
            </Link>
            <Link href="/me" className="hover:text-ink">
              My Haggle
            </Link>
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {user ? (
            <>
              {user.image && (
                <Image
                  src={user.image}
                  alt=""
                  width={28}
                  height={28}
                  className="rounded-full"
                  unoptimized
                />
              )}
              <span className="hidden sm:inline">{user.name}</span>
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/" });
                }}
              >
                <button className="text-muted hover:text-ink">Sign out</button>
              </form>
            </>
          ) : (
            <Link href="/signin" className="font-medium text-accent hover:underline">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
