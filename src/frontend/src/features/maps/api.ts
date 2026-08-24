import type { LocationResult, RouteResult, ResolveTripResult } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function getHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const authToken = token || localStorage.getItem('access_token');
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  return headers;
}

export async function searchPlaces(
  query: string,
  options?: {
    city?: string;
    limit?: number;
    sessionId?: string;
    token?: string;
    signal?: AbortSignal;
  }
): Promise<LocationResult[]> {
  if (!query || query.trim().length === 0) return [];
  const params = new URLSearchParams({
    q: query.trim(),
    limit: String(options?.limit || 5),
  });
  if (options?.city) params.set('city', options.city);
  if (options?.sessionId) params.set('session_id', options.sessionId);

  const url = `${API_BASE}/api/v1/maps/search?${params.toString()}`;
  const response = await fetch(url, {
    headers: getHeaders(options?.token),
    signal: options?.signal,
  });

  if (!response.ok) {
    throw new Error(`Place search failed: ${response.status}`);
  }

  const data = await response.json();
  return (data.results || data.candidates || []) as LocationResult[];
}

export async function reverseGeocode(
  lat: number,
  lon: number,
  options?: {
    sessionId?: string;
    token?: string;
    signal?: AbortSignal;
  }
): Promise<LocationResult | null> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });
  if (options?.sessionId) params.set('session_id', options.sessionId);

  const url = `${API_BASE}/api/v1/maps/reverse?${params.toString()}`;
  const response = await fetch(url, {
    headers: getHeaders(options?.token),
    signal: options?.signal,
  });

  if (!response.ok) {
    throw new Error(`Reverse geocode failed: ${response.status}`);
  }

  const data = await response.json();
  const list = (data.results || data.candidates || []) as LocationResult[];
  return list.length > 0 ? list[0] : null;
}

export async function calculateRoute(params: {
  pickup?: { lat: number; lon: number };
  destination?: { lat: number; lon: number };
  pickupPlaceId?: string;
  destinationPlaceId?: string;
  sessionId?: string;
  profile?: string;
  token?: string;
}): Promise<RouteResult> {
  const payload: Record<string, any> = {
    session_id: params.sessionId,
    profile: params.profile || 'driving',
  };

  if (params.pickup && params.destination) {
    payload.pickup = params.pickup;
    payload.destination = params.destination;
  } else if (params.pickupPlaceId && params.destinationPlaceId) {
    payload.pickup_place_id = params.pickupPlaceId;
    payload.destination_place_id = params.destinationPlaceId;
  } else {
    throw new Error('Either coordinates or place IDs must be provided');
  }

  const response = await fetch(`${API_BASE}/api/v1/maps/route`, {
    method: 'POST',
    headers: getHeaders(params.token),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData?.detail?.error?.message ||
        errorData?.detail?.message ||
        `Route calculation failed: ${response.status}`
    );
  }

  return response.json() as Promise<RouteResult>;
}

export async function resolveTrip(params: {
  pickup: string | { lat: number; lon: number };
  destination: string | { lat: number; lon: number };
  city?: string;
  sessionId?: string;
  token?: string;
}): Promise<ResolveTripResult> {
  const payload = {
    pickup: params.pickup,
    destination: params.destination,
    city: params.city || 'Hà Nội',
    session_id: params.sessionId,
  };

  const response = await fetch(`${API_BASE}/api/v1/maps/resolve-trip`, {
    method: 'POST',
    headers: getHeaders(params.token),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData?.detail?.error?.message ||
        errorData?.detail?.message ||
        `Resolve trip failed: ${response.status}`
    );
  }

  return response.json() as Promise<ResolveTripResult>;
}
