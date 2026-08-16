"""AloSM Maps subsystem — geocoding, routing, service area and place resolution.

Architecture:
    Frontend/Agent → AloSM API → MapsService → GeocodingProvider / RoutingProvider
                                                       ↓                  ↓
                                                   Nominatim           OSRM
                                                       ↓                  ↓
                                                   OpenStreetMap Vietnam (.osm.pbf)

Public consumers MUST NOT call Nominatim/OSRM directly; all access flows through
the MapsService and the public API endpoints in ``src.backend.api.routes.maps``.
"""
