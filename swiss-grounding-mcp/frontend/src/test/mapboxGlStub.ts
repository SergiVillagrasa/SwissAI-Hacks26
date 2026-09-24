// Test-only stand-in for the real mapbox-gl package: mapbox-gl's real
// bundle assumes a browser WebGL environment and fails to even load
// under jsdom. Any test that imports a component depending on
// mapbox-gl transitively (e.g. via the widget registry) gets this
// harmless stub instead, via the `resolve.alias` in vite.config.ts
// (test mode only). Tests that assert on map/marker behavior
// (RouteMap.test.tsx, TrainConnectionsCard.test.tsx) still use their
// own `vi.mock("mapbox-gl", ...)`, which takes precedence over this
// alias for those files.
class StubMap {
  on() {}
  remove() {}
  addControl() {}
}

class StubMarker {
  setLngLat() {
    return this;
  }
  addTo() {
    return this;
  }
}

export default { accessToken: "", Map: StubMap, Marker: StubMarker };
