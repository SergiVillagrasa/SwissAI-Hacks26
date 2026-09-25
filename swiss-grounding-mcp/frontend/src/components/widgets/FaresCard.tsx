import { GlassTile, glassRow } from "../GlassTile";
import { SortBadge } from "./SortBadge";

interface FareProduct {
  product: string;
  price_chf: number;
  class_of_travel: string;
  discount: string | null;
}

export interface FareSearchData {
  fares: FareProduct[];
  booking_url: string | null;
  sorted_by?: string | null;
}

function BookOnSbbButton({ bookingUrl }: { bookingUrl: string | null }) {
  if (!bookingUrl) return null;
  return (
    <a
      href={bookingUrl}
      target="_blank"
      rel="noreferrer"
      aria-label="Book on SBB, opens the official SBB website in a new tab"
      className="inline-block rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
    >
      Book on SBB
    </a>
  );
}

export function FaresCard({ data }: { data: FareSearchData }) {
  if (data.fares.length > 0) {
    return (
      <GlassTile className="space-y-2 p-4">
        <SortBadge sortedBy={data.sorted_by} />
        <ul className="space-y-2">
          {data.fares.map((fare, index) => (
            <li
              key={index}
              className={`flex items-center justify-between p-3 text-sm ${glassRow}`}
            >
              <span className="text-neutral-700">
                {fare.product}
                {fare.discount ? ` (${fare.discount})` : ""}
              </span>
              <span className="tabular font-semibold text-accent-ink">CHF {fare.price_chf}</span>
            </li>
          ))}
        </ul>
        <BookOnSbbButton bookingUrl={data.booking_url} />
      </GlassTile>
    );
  }

  return (
    <GlassTile className="flex items-center justify-center p-4">
      <BookOnSbbButton bookingUrl={data.booking_url} />
    </GlassTile>
  );
}
