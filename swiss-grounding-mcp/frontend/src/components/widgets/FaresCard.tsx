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
      <ul className="space-y-2">
        {data.fares.map((fare, index) => (
          <li key={index} className="flex items-center justify-between rounded-xl border border-neutral-200 p-3">
            <span>{fare.product}{fare.discount ? ` (${fare.discount})` : ""}</span>
            <span className="font-medium">CHF {fare.price_chf}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <a
      href={data.booking_url ?? undefined}
      target="_blank"
      rel="noreferrer"
      className="inline-block rounded-full bg-accent px-4 py-2 text-sm font-medium text-white"
    >
      Book on SBB
    </a>
  );
}
