import "server-only";

import { createHash, createHmac } from "node:crypto";
import { redirect } from "next/navigation";

import { auth } from "@/auth";

/**
 * Calls the Haggle backend as the signed-in student.
 *
 * Runs only on the server. Every request is HMAC-signed with a secret the browser
 * never sees and names the Discord user from the session, matching
 * `src/web_api.py` (canonical string: ts, method, path, query, user, sha256(body)).
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function sign(ts: string, method: string, path: string, query: string, user: string, body: string) {
  const digest = createHash("sha256").update(body).digest("hex");
  const canonical = `${ts}\n${method}\n${path}\n${query}\n${user}\n${digest}`;
  return createHmac("sha256", process.env.HAGGLE_HMAC_SECRET!).update(canonical).digest("hex");
}

export async function currentUserId(): Promise<string> {
  const session = await auth();
  if (!session?.user?.id) redirect("/signin");
  return session.user.id;
}

export async function api<T>(
  method: "GET" | "POST" | "PUT",
  path: string,
  options: { query?: Record<string, string | undefined>; body?: unknown } = {},
): Promise<T> {
  const user = await currentUserId();
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(options.query ?? {})) if (v) params.set(k, v);
  const query = params.toString();
  const body = options.body === undefined ? "" : JSON.stringify(options.body);
  const ts = Math.floor(Date.now() / 1000).toString();

  const res = await fetch(`${process.env.HAGGLE_API_URL}${path}${query ? `?${query}` : ""}`, {
    method,
    body: body || undefined,
    cache: "no-store",
    headers: {
      "content-type": "application/json",
      "x-haggle-user": user,
      "x-haggle-timestamp": ts,
      "x-haggle-signature": sign(ts, method, path, query, user, body),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error ?? "Something went wrong");
  return data as T;
}
