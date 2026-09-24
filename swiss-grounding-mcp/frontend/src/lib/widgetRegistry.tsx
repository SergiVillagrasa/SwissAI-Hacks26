import type { ComponentType } from "react";
import { TrainConnectionsCard } from "../components/widgets/TrainConnectionsCard";
import { StationBoardCard } from "../components/widgets/StationBoardCard";
import { FaresCard } from "../components/widgets/FaresCard";
import { DisruptionsCard } from "../components/widgets/DisruptionsCard";
import { FlightCard } from "../components/widgets/FlightCard";
import { AirportGuidanceCard } from "../components/widgets/AirportGuidanceCard";
import { FlightToTrainCard } from "../components/widgets/FlightToTrainCard";

export const WIDGET_COMPONENTS: Record<string, ComponentType<any>> = {
  train_connections: TrainConnectionsCard,
  station_board: StationBoardCard,
  fares: FaresCard,
  disruptions: DisruptionsCard,
  flight: FlightCard,
  flight_search: FlightCard,
  airport_guidance: AirportGuidanceCard,
  flight_to_train: FlightToTrainCard,
};

export const DISPLAYABLE_STATUSES: Record<string, string[]> = {
  train_connections: ["ok"],
  station_board: ["ok"],
  fares: ["success", "fallback_link"],
  disruptions: ["ok"],
  flight: ["answered"],
  flight_search: ["answered"],
  airport_guidance: ["answered"],
  flight_to_train: ["answered"],
};

export const WIDGET_TYPE_BY_TOOL: Record<string, string> = {
  find_connections: "train_connections",
  find_disruptions: "disruptions",
  get_station_board: "station_board",
  check_public_transport_fares: "fares",
  find_flight_by_number: "flight",
  search_airport_flights: "flight_search",
  get_airport_guidance: "airport_guidance",
  connect_flight_to_train: "flight_to_train",
};
