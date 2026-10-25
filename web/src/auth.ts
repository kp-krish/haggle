import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";

const DISCORD_API = "https://discord.com/api/v10";

type Membership = { nick?: string | null } | null;

/** The student's membership in the Haggle server, or null if they aren't in it. */
async function haggleMembership(accessToken: string): Promise<Membership> {
  const res = await fetch(
    `${DISCORD_API}/users/@me/guilds/${process.env.DISCORD_GUILD_ID}/member`,
    { headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store" },
  );
  if (!res.ok) return null;
  return res.json();
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Discord({
      // Discord now returns iss=https://discord.com on the callback (RFC 9207); without
      // this, Auth.js compares it to a placeholder issuer and rejects the sign-in.
      issuer: "https://discord.com",
      // guilds.members.read lets us check the student is in the campus server.
      authorization: { params: { scope: "identify guilds.members.read" } },
    }),
  ],
  pages: { signIn: "/signin", error: "/signin" },
  session: { strategy: "jwt" },
  callbacks: {
    async signIn({ account }) {
      if (!account?.access_token) return false;
      const member = await haggleMembership(account.access_token);
      return member ? true : "/signin?error=not-member";
    },
    async jwt({ token, profile }) {
      // Only on sign-in: keep the Discord id and how they appear in the server.
      if (profile) {
        const p = profile as {
          id: string;
          username: string;
          global_name?: string | null;
          avatar?: string | null;
        };
        token.discordId = p.id;
        token.name = p.global_name || p.username;
        token.picture = p.avatar
          ? `https://cdn.discordapp.com/avatars/${p.id}/${p.avatar}.png?size=64`
          : null;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.discordId as string;
      return session;
    },
  },
});
