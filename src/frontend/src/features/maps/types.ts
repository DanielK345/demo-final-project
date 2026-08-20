export interface AddressDetails {
  road?: string | null;
  ward?: string | null;
  district?: string | null;
  city?: string | null;
  province?: string | null;
  country?: string | null;
}

export interface LocationResult {
  id: string;
  name: string;
  display_name: string;
  lat: number;
  lon: number;
  latitude?: number;
  longitude?: number;
  address?: AddressDetails;
  formatted_address?: string;
  provider_place_id?: string;
  types?: string[];
  serviceable?: boolean | null;
  provider?: string;
}

export interface GeoJSONGeometry {
  type: 'LineString';
  coordinates: [number, number][]; // [lon, lat] in GeoJSON standard
}

export interface RouteLeg {
  distance?: number;
  duration?: number;
  summary?: string;
  steps?: any[];
}

export interface RouteResult {
  route_id: string;
  distance_m: number;
  distance_km: number;
  duration_s: number;
  duration_minutes: number;
  distance_meters?: number;
  duration_seconds?: number;
  geometry?: GeoJSONGeometry;
  legs?: RouteLeg[];
  traffic_status?: string;
  provider?: string;
  created_at?: string | null;
  expires_at?: string | null;
}

export interface ResolveTripResult {
  pickup: LocationResult;
  destination: LocationResult;
  route: RouteResult;
}
