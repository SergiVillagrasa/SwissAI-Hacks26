import { useState } from "react";
import { GlassTile, glassRow, glassRowSelected } from "../GlassTile";
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

export function BookOnSbbButton({ bookingUrl }: { bookingUrl: string | null | undefined }) {
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
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  if (data.fares.length > 0) {
    return (
      <GlassTile className="space-y-2 p-4">
        <SortBadge sortedBy={data.sorted_by} />
        <ul className="space-y-2">
          {data.fares.map((fare, index) => {
            const isSelected = selectedIndex === index;
            return (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => setSelectedIndex((current) => (current === index ? null : index))}
                  aria-expanded={isSelected}
                  className={`flex w-full cursor-pointer items-center justify-between p-3 text-left text-sm transition duration-200 hover:bg-blue-50/60 ${glassRow} ${isSelected ? glassRowSelected : ""}`}
                >
                  <span className="text-neutral-700">
                    {fare.product}
                    {fare.discount ? ` (${fare.discount})` : ""}
                  </span>
                  <span className="tabular font-semibold text-accent-ink">CHF {fare.price_chf}</span>
                </button>
                {isSelected && (
                  <div className="mt-1 rounded-2xl border border-blue-200/70 bg-blue-50/40 p-3 text-xs text-neutral-600">
                    <span className="font-semibold text-neutral-700">Class of travel:</span> {fare.class_of_travel}
                    {fare.discount && (
                      <>
                        {" · "}
                        <span className="font-semibold text-neutral-700">Discount:</span> {fare.discount}
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
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
