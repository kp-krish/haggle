"use client";

import { useActionState } from "react";

import { expressInterest, type FormState } from "@/app/actions";
import { AreaField, StyleField, WindowsField } from "@/components/choice-fields";
import { Button, Field, INPUT } from "@/components/ui";
import type { Profile } from "@/lib/types";

export function InterestForm({
  listingId,
  asking,
  profile,
}: {
  listingId: string;
  asking: number;
  profile: Profile;
}) {
  const [state, action, pending] = useActionState<FormState, FormData>(
    expressInterest.bind(null, listingId),
    undefined,
  );

  if (state?.ok) {
    return (
      <p role="status" className="rounded-md bg-ok-soft px-4 py-3 text-sm text-ok">
        {state.ok}
      </p>
    );
  }

  return (
    <form action={action} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Start at" hint="Your agent's first offer.">
          <input
            name="min"
            inputMode="numeric"
            placeholder={String(Math.floor(asking * 0.6))}
            className={`${INPUT} tabular`}
            required
          />
        </Field>
        <Field label="Your max" hint="Private. Never shown to the seller.">
          <input
            name="max"
            inputMode="numeric"
            placeholder={String(asking)}
            className={`${INPUT} tabular`}
            required
          />
        </Field>
      </div>
      <WindowsField defaultValue={profile.windows} />
      <AreaField defaultValue={profile.area} />
      <StyleField defaultValue={profile.style} />
      {state?.error && (
        <p role="alert" className="text-sm text-bad">
          {state.error}
        </p>
      )}
      <Button className="w-full" disabled={pending}>
        {pending ? "Starting…" : "Start haggling"}
      </Button>
      <p className="text-xs text-muted">
        The negotiation happens in your Discord messages. Nothing is final until you
        and the seller both confirm.
      </p>
    </form>
  );
}
