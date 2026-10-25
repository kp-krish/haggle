import { Field, INPUT } from "@/components/ui";
import { areaLabel } from "@/lib/format";

const AREAS = ["any", "north", "central", "south"];
const STYLES = [
  { value: "patient", label: "Patient", hint: "Holds out, concedes late" },
  { value: "balanced", label: "Balanced", hint: "Meets in the middle" },
  { value: "quick", label: "Quick", hint: "Concedes early, closes fast" },
];

export function AreaField({ defaultValue = "any" }: { defaultValue?: string }) {
  return (
    <Field label="Where on campus are you?" hint="Used to pick a meeting spot near you both.">
      <select name="area" defaultValue={defaultValue} className={INPUT}>
        {AREAS.map((a) => (
          <option key={a} value={a}>
            {a === "any" ? "No preference" : areaLabel(a)}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function WindowsField({ defaultValue = "" }: { defaultValue?: string }) {
  return (
    <Field label="When can you meet in the next few days?" hint="Only the final pickup time is shared.">
      <textarea
        name="windows"
        rows={2}
        defaultValue={defaultValue}
        placeholder="Weekdays after 3, Saturday morning"
        className={INPUT}
      />
    </Field>
  );
}

export function StyleField({ defaultValue = "balanced" }: { defaultValue?: string }) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="font-display text-sm font-semibold uppercase tracking-wider">How should your agent negotiate?</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {STYLES.map((s) => (
          <label
            key={s.value}
            className="flex cursor-pointer flex-col border-2 border-line bg-card px-3 py-2 text-sm has-[:checked]:border-pin has-[:checked]:bg-pin/5"
          >
            <span className="flex items-center gap-2 font-medium">
              <input
                type="radio"
                name="style"
                value={s.value}
                defaultChecked={s.value === defaultValue}
                className="accent-pin"
              />
              {s.label}
            </span>
            <span className="text-xs text-muted">{s.hint}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
