import { Field, INPUT } from "@/components/ui";
import { areaLabel } from "@/lib/format";

const AREAS = ["any", "north", "central", "south"];
const STYLES = [
  { value: "patient", label: "Patient", hint: "holds out, concedes late" },
  { value: "balanced", label: "Balanced", hint: "meets in the middle" },
  { value: "quick", label: "Quick", hint: "concedes early, closes fast" },
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
    <Field label="When can you meet in the next few days?" hint="Only the final pickup time is ever shared.">
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
      <legend className="text-sm font-semibold">How should your agent negotiate?</legend>
      <div className="grid gap-1">
        {STYLES.map((s) => (
          <label key={s.value} className="flex cursor-pointer items-baseline gap-2 text-[15px]">
            <input
              type="radio"
              name="style"
              value={s.value}
              defaultChecked={s.value === defaultValue}
              className="translate-y-px accent-pine"
            />
            <span>
              {s.label} <span className="text-muted">{s.hint}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
