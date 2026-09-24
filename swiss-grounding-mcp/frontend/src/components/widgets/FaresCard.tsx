import { GlassTile, glassRow } from "../GlassTile";

interface FareProduct {
  product: string;
  price_chf: number;
  class_of_travel: string;
  discount: string | null;
}

export interface FareSearchData {
  fares: FareProduct[];
  booking_url: string | null;
}

export function FaresCard({ data }: { data: FareSearchData }) {
  if (data.fares.length > 0) {
    return (
      <GlassTile className="space-y-2 p-4">
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
      </GlassTile>
    );
  }

  return (
    <GlassTile className="flex items-center justify-center p-4">
      <a
        href={data.booking_url ?? undefined}
        target="_blank"
        rel="noreferrer"
        className="inline-block rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
      >
        Book on SBB
      </a>
    </GlassTile>
  );
}
