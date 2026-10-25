"use client";

import { useState } from "react";

import { createListing, startUpload } from "@/app/actions";
import { AreaField, StyleField, WindowsField } from "@/components/choice-fields";
import { Button, Field, INPUT } from "@/components/ui";
import type { Profile } from "@/lib/types";

const MAX_BYTES = 10 * 1024 * 1024;

export function SellForm({ profile }: { profile: Profile }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"idle" | "uploading" | "saving">("idle");

  function onPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setError(null);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(file ? URL.createObjectURL(file) : null);
    if (file && file.size > MAX_BYTES) setError("That photo is over 10 MB. Try a smaller one.");
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const photo = form.get("photo");
    if (!(photo instanceof File) || !photo.size) return setError("Add a photo of the item.");
    if (photo.size > MAX_BYTES) return setError("That photo is over 10 MB. Try a smaller one.");
    setError(null);

    // 1. Upload the photo straight to storage with a one-time upload form.
    setStep("uploading");
    const slot = await startUpload(photo.type || "image/jpeg");
    if ("error" in slot) {
      setStep("idle");
      return setError(slot.error);
    }
    const upload = new FormData();
    Object.entries(slot.upload.fields).forEach(([k, v]) => upload.append(k, v));
    upload.append("file", photo);
    const res = await fetch(slot.upload.url, { method: "POST", body: upload });
    if (!res.ok) {
      setStep("idle");
      return setError("The photo didn't upload. Try again.");
    }

    // 2. Create the listing; the page it redirects to shows progress.
    setStep("saving");
    form.delete("photo");
    form.set("photo_key", slot.key);
    const result = await createListing(form);
    if (result?.error) {
      setStep("idle");
      setError(result.error);
    }
  }

  const busy = step !== "idle";

  return (
    <form onSubmit={onSubmit} className="grid gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-2">
        <span className="block text-sm font-semibold">Photo</span>
        <label className="relative flex aspect-square max-w-full cursor-pointer items-center justify-center overflow-hidden bg-wash text-sm text-muted hover:outline hover:outline-ink">
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img src={preview} alt="Your item" className="absolute inset-0 size-full object-cover" />
          ) : (
            <span className="underline underline-offset-4">Choose a photo</span>
          )}
          <input
            type="file"
            name="photo"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            onChange={onPhoto}
            className="sr-only"
          />
        </label>
        <p className="text-[13px] text-muted">
          A clear, well-lit photo. We&apos;ll write the title and description from it.
        </p>
      </div>

      <div className="space-y-5">
        <Field label="A few words about it" hint="What it is, and anything worth knowing about its condition.">
          <textarea
            name="description"
            rows={3}
            maxLength={300}
            required
            placeholder="Mini fridge, 3.1 cu ft, small dent on the side"
            className={INPUT}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Asking price" hint="Shown to everyone.">
            <input name="asking" inputMode="numeric" required placeholder="70" className={`${INPUT} tabular`} />
          </Field>
          <Field label="Lowest you'll take" hint="Private. Only your agent sees it.">
            <input name="floor" inputMode="numeric" required placeholder="45" className={`${INPUT} tabular`} />
          </Field>
        </div>
        <WindowsField defaultValue={profile.windows} />
        <AreaField defaultValue={profile.area} />
        <StyleField defaultValue={profile.style} />
        {error && (
          <p role="alert" className="text-sm text-bad">
            {error}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-4 border-t border-line pt-5">
          <Button disabled={busy}>
            {step === "uploading" ? "Uploading photo…" : step === "saving" ? "Saving…" : "Continue"}
          </Button>
          <span className="text-[13px] text-muted">You&apos;ll see a preview before anything is published.</span>
        </div>
      </div>
    </form>
  );
}
