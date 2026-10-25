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
  place_id?: string;
  spot_name?: string;
  cancelled_by?: "seller" | "buyer";
  has_recap?: boolean;
  created_at: string;
  source?: string;
};

export type LadderStep = { round: number; side: "seller" | "buyer"; amount: number; accept: boolean };

export type Recap = Deal & {
  agreed_price: number;
  ladder: LadderStep[];
  rounds: number;
  saving: number;
  reward: {
    points: { reason: string; points: number }[];
    achievements: { id: string; label: string; detail: string }[];
    rank: string | null;
    ranked_up: boolean;
  } | null;
};

export type Rank = { name: string; points: number; next: string | null; to_next: number; progress: number };
export type Achievement = { id: string; label: string; detail: string; earned_at: string | null };
export type Game = { rank: Rank; ranks: { name: string; points: number }[]; achievements: Achievement[] };

export type ZoneScores = { since: string; scores: Record<string, number>; leader: string | null };

export type Profile = {
  badges: Badge[];
  stats: { pickups: number; as_seller: number; as_buyer: number; no_shows: number; cancelled: number };
  area: string;
  windows: string;
  style: string;
  paused: boolean;
  game: Game;
};

export type BoardRow = {
  deal_id: string | null;
  listing_id: string;
  title: string;
  asking: number;
  state: string;
  rounds: number;
  price: number | null;
  mine: boolean;
  side?: "seller" | "buyer";
  seller_offer?: number | null;
  buyer_offer?: number | null;
  updated_at: string;
};

export type Area = { label: string; lat: number; lng: number; bounds: [[number, number], [number, number]] };
export type Place = {
  place_id: string;
  name: string;
  area: string;
  lat: number;
  lng: number;
  curbside: boolean;
};
export type PlacesResponse = { areas: Record<string, Area>; places: Place[] };

export type BrowseResponse = { listings: Listing[]; categories: string[]; areas: string[] };
export type MeResponse = { profile: Profile; listings: Listing[]; deals: Deal[] };
