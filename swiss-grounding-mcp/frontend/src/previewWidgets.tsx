// TEMPORARY manual visual-verification harness. Not part of the app; delete
// after confirming the selectable-row/detail pattern renders correctly.
import { createRoot } from "react-dom/client";
import "./index.css";
import { TrainConnectionsCard } from "./components/widgets/TrainConnectionsCard";
import { FlightCard } from "./components/widgets/FlightCard";
import { FlightToTrainCard } from "./components/widgets/FlightToTrainCard";
import { FaresCard } from "./components/widgets/FaresCard";
import { StationBoardCard } from "./components/widgets/StationBoardCard";

const trainData = {
  connections: [
    {
      departure: "2026-09-25T08:02:00+02:00",
      arrival: "2026-09-25T09:00:00+02:00",
      duration_minutes: 58,
      changes: 1,
      origin_latitude: 47.3769,
      origin_longitude: 8.5417,
      destination_latitude: 46.9481,
      destination_longitude: 7.4474,
      legs: [
        { mode: "rail", line: "IC 1", from_name: "Zürich HB", to_name: "Bern", departure: "2026-09-25T08:02:00+02:00", arrival: "2026-09-25T08:58:00+02:00" },
        { mode: "walk", line: null, from_name: "Bern", to_name: "Bern", departure: null, arrival: null },
      ],
    },
    {
      departure: "2026-09-25T08:32:00+02:00",
      arrival: "2026-09-25T09:34:00+02:00",
      duration_minutes: 62,
      changes: 0,
      origin_latitude: null,
      origin_longitude: null,
      destination_latitude: null,
      destination_longitude: null,
      legs: [
        { mode: "rail", line: "IC 8", from_name: "Zürich HB", to_name: "Bern", departure: "2026-09-25T08:32:00+02:00", arrival: "2026-09-25T09:34:00+02:00" },
      ],
    },
  ],
  provenance: { source: "OJP 2.0", source_url: "https://opentransportdata.swiss", retrieved_at: "2026-09-25T07:00:00Z" },
  sorted_by: "duration",
  via_stop_name: "Berna",
};

const flightData = {
  flights: [
    {
      flight_number: "LX14",
      flight_date: "2026-09-25",
      airline: { name: "SWISS", iata: "LX", icao: "SWR" },
      departure: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T10:20:00+02:00", estimated: null, actual: null, terminal: "1", gate: "A12", delay_minutes: 5 },
      arrival: { airport: { iata: "JFK", icao: "KJFK", name: "John F. Kennedy Intl", timezone: null }, scheduled: "2026-09-25T14:10:00-04:00", estimated: null, actual: null, terminal: "4", gate: null, delay_minutes: null },
      flight_status: "scheduled",
      booking_url: "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25",
    },
    {
      flight_number: "LX16",
      flight_date: "2026-09-25",
      airline: { name: "SWISS", iata: "LX", icao: "SWR" },
      departure: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T13:00:00+02:00", estimated: null, actual: null, terminal: "1", gate: "A9", delay_minutes: null },
      arrival: { airport: { iata: "JFK", icao: "KJFK", name: "John F. Kennedy Intl", timezone: null }, scheduled: "2026-09-25T16:45:00-04:00", estimated: null, actual: null, terminal: "4", gate: null, delay_minutes: null },
      flight_status: "delayed",
      booking_url: "https://www.swiss.com/ch/en/book-flights",
    },
  ],
};

const flightToTrainData = {
  message: "Considering onward trains departing no earlier than 15:10 (60-minute transfer buffer).",
  flight: flightData.flights[0],
  train_connections: trainData.connections,
  train_booking_url: "https://sbb.ch/en?von=Z%C3%BCrich%20Flughafen&nach=Bern&date=2026-09-25",
  train_price_chf: 19.8,
};

const faresData = {
  fares: [
    { product: "Saver Day Pass", price_chf: 29, class_of_travel: "2nd class", discount: null },
    { product: "Half-Fare Fare", price_chf: 19.8, class_of_travel: "2nd class", discount: "Halbtax" },
  ],
  booking_url: "https://sbb.ch/en",
  sorted_by: "price",
};

const stationBoardData = {
  station_name: "Bern",
  event_type: "departures",
  events: [
    { line: "IC 1", mode: "rail", direction_name: "Genève-Aéroport", planned_time: "2026-09-25T09:05:00+02:00", estimated_time: "2026-09-25T09:07:00+02:00", platform: "3", delay_minutes: 2 },
    { line: "S1", mode: "rail", direction_name: "Fribourg", planned_time: "2026-09-25T09:10:00+02:00", estimated_time: null, platform: "7", delay_minutes: null },
  ],
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "2rem" }}>
      <h2 style={{ font: "600 14px sans-serif", marginBottom: "0.5rem" }}>{title}</h2>
      {children}
    </div>
  );
}

function Preview() {
  return (
    <div style={{ maxWidth: 640, margin: "2rem auto", display: "flex", flexDirection: "column", gap: "1rem" }}>
      <Section title="TrainConnectionsCard">
        <TrainConnectionsCard data={trainData} onSelect={() => {}} />
      </Section>
      <Section title="FlightCard (multi)">
        <FlightCard data={flightData} onSelect={() => {}} />
      </Section>
      <Section title="FlightToTrainCard">
        <FlightToTrainCard data={flightToTrainData} onSelectConnection={() => {}} />
      </Section>
      <Section title="FaresCard">
        <FaresCard data={faresData} />
      </Section>
      <Section title="StationBoardCard">
        <StationBoardCard data={stationBoardData} />
      </Section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<Preview />);
