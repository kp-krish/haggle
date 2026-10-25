import type { Tone } from "@/components/ui";

const CATEGORY_LABELS: Record<string, string> = {
  "bikes-transport": "Bikes & transport",
  "sports-outdoors": "Sports & outdoors",
};

export function categoryLabel(category?: string): string {
  if (!category) return "Other";
  return CATEGORY_LABELS[category] ?? category.charAt(0).toUpperCase() + category.slice(1);
}

export function areaLabel(area?: string): string {
  if (!area || area === "any") return "Anywhere on campus";
  return `${area.charAt(0).toUpperCase()}${area.slice(1)} campus`;
}

/** "North", "Central", "South" or "Anywhere": for compact meta lines. */
export function areaShort(area?: string): string {
  if (!area || area === "any") return "Anywhere";
  return `${area.charAt(0).toUpperCase()}${area.slice(1)}`;
}

export function money(amount: number): string {
  return `$${amount.toLocaleString("en-US")}`;
}

export function since(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

/** How a deal's state reads to the student, and what colour it gets. */
export function dealStatus(state: string, pickup?: string): { label: string; tone: Tone } {
  switch (state) {
    case "proposed":
      return { label: "Waiting for you to start, in Discord", tone: "live" };
    case "starting":
    case "negotiating":
      return { label: "Negotiating in Discord", tone: "live" };
    case "scheduling":
      return { label: "Price agreed, finding a pickup time", tone: "warn" };
    case "confirming":
      return { label: "Waiting for both of you to confirm", tone: "warn" };
    case "confirmed":
      return { label: pickup ? `Pickup ${pickup}` : "Confirmed", tone: "ok" };
    case "done":
      return { label: "Completed", tone: "ok" };
    case "no_deal":
      return { label: "No deal", tone: "neutral" };
    case "no_show":
      return { label: "Pickup didn't happen", tone: "bad" };
    default:
      return { label: "Closed", tone: "neutral" };
  }
}

export function listingStatus(status: string): { label: string; tone: Tone } {
  switch (status) {
    case "processing":
      return { label: "Writing your listing", tone: "warn" };
    case "preview":
      return { label: "Ready to publish", tone: "live" };
    case "publishing":
      return { label: "Publishing", tone: "warn" };
    case "open":
      return { label: "Live", tone: "ok" };
    case "sold":
      return { label: "Sold", tone: "neutral" };
    case "rejected":
      return { label: "Can't be listed", tone: "bad" };
    case "error":
      return { label: "Something went wrong", tone: "bad" };
    default:
      return { label: "Taken down", tone: "neutral" };
  }
}
