import { auth } from "@/auth";
import { api } from "@/lib/api";
import type { BoardRow } from "@/lib/types";

/** The live board, polled by the browser. Signed-in students only. */
export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return Response.json({ error: "sign in" }, { status: 401 });
  const data = await api<{ rows: BoardRow[] }>("GET", "/web/board");
  return Response.json(data, { headers: { "cache-control": "no-store" } });
}
