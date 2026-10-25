/** Shapes returned by the backend's website API (src/web_api.py). */

export type Badge = { id: string; label: string; detail: string };

export type Listing = {
  listing_id: string;
  title?: string;
  description?: string;
  asking: number;
  category?: string;
  area: string;
  large?: boolean;
  status: string;
  photo: string | null;
  mine: boolean;
  seller_badges: Badge[];
  created_at: string;
  source?: string;
  rejected_reason?: string | null;
  my_deal?: Deal | null;
};

export type Deal = {
  deal_id: string;
  listing_id: string;
  title?: string;
  asking: number;
  state: string;
  side: "seller" | "buyer";
  agreed_price?: number;
  pickup?: string;
  created_at: string;
  source?: string;
};

export type Profile = {
  badges: Badge[];
  stats: { pickups: number; as_seller: number; as_buyer: number; no_shows: number };
  area: string;
  windows: string;
  style: string;
  paused: boolean;
};

export type BrowseResponse = { listings: Listing[]; categories: string[]; areas: string[] };
export type MeResponse = { profile: Profile; listings: Listing[]; deals: Deal[] };
