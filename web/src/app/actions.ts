"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/api";

/** Each action re-reads the session (inside `api`), so it authorizes itself. */

export type FormState = { error?: string; ok?: string } | undefined;

function failure(e: unknown): FormState {
  if (e instanceof ApiError) return { error: e.message };
  throw e;
}

const text = (form: FormData, key: string) => String(form.get(key) ?? "").trim();

export async function startUpload(contentType: string) {
  try {
    return await api<{ upload: { url: string; fields: Record<string, string> }; key: string }>(
      "POST",
      "/web/uploads",
      { body: { content_type: contentType } },
    );
  } catch (e) {
    return failure(e) as { error: string };
  }
}

export async function createListing(form: FormData): Promise<FormState> {
  let listingId: string;
  try {
    const res = await api<{ listing_id: string }>("POST", "/web/listings", {
      body: {
        photo_key: text(form, "photo_key"),
        description: text(form, "description"),
        asking: text(form, "asking"),
        floor: text(form, "floor"),
        area: text(form, "area"),
        windows: text(form, "windows"),
        style: text(form, "style"),
      },
    });
    listingId = res.listing_id;
  } catch (e) {
    return failure(e);
  }
  redirect(`/listings/${listingId}`);
}

async function listingAction(listingId: string, verb: "publish" | "discard" | "stop") {
  try {
    await api("POST", `/web/listings/${listingId}/${verb}`);
  } catch (e) {
    return failure(e);
  }
  revalidatePath(`/listings/${listingId}`);
  revalidatePath("/me");
}

export async function publishListing(listingId: string) {
  return listingAction(listingId, "publish");
}

export async function discardListing(listingId: string) {
  const result = await listingAction(listingId, "discard");
  if (!result?.error) redirect("/me");
  return result;
}

export async function stopListing(listingId: string) {
  return listingAction(listingId, "stop");
}

export async function stopDeal(dealId: string) {
  try {
    await api("POST", `/web/deals/${dealId}/stop`);
  } catch (e) {
    return failure(e);
  }
  revalidatePath("/me");
}

export async function expressInterest(
  listingId: string,
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  try {
    await api("POST", `/web/listings/${listingId}/interest`, {
      body: {
        min: text(form, "min"),
        max: text(form, "max"),
        area: text(form, "area"),
        windows: text(form, "windows"),
        style: text(form, "style"),
      },
    });
  } catch (e) {
    return failure(e);
  }
  revalidatePath(`/listings/${listingId}`);
  return { ok: "Your agent is on it. Check your Discord messages to follow along." };
}

export async function savePreferences(_prev: FormState, form: FormData): Promise<FormState> {
  try {
    await api("PUT", "/web/me/preferences", {
      body: { area: text(form, "area"), windows: text(form, "windows"), style: text(form, "style") },
    });
  } catch (e) {
    return failure(e);
  }
  revalidatePath("/me");
  return { ok: "Saved." };
}
