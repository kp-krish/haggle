"use client";

import { useActionState } from "react";

import { savePreferences, type FormState } from "@/app/actions";
import { AreaField, StyleField, WindowsField } from "@/components/choice-fields";
import { Button } from "@/components/ui";
import type { Profile } from "@/lib/types";

export function PreferencesForm({ profile }: { profile: Profile }) {
  const [state, action, pending] = useActionState<FormState, FormData>(savePreferences, undefined);
  return (
    <form action={action} className="space-y-4">
      <WindowsField defaultValue={profile.windows} />
      <AreaField defaultValue={profile.area} />
      <StyleField defaultValue={profile.style} />
      <div className="flex items-center gap-3">
        <Button variant="secondary" disabled={pending}>
          {pending ? "Saving…" : "Save defaults"}
        </Button>
        {state?.ok && <span className="text-sm text-ok">{state.ok}</span>}
        {state?.error && <span className="text-sm text-bad">{state.error}</span>}
      </div>
    </form>
  );
}
