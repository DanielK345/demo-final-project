import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { LocationResult, RouteResult } from '../types';

function MapBoundsUpdater({
  pickup,
  destination,
  routeCoordinates,
}: {
  pickup?: LocationResult | { lat: number; lon: number } | null;
  destination?: LocationResult | { lat: number; lon: number } | null;
  routeCoordinates?: [number, number][];
}) {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];

    if (pickup && typeof pickup.lat === 'number' && typeof pickup.lon === 'number') {
      points.push([pickup.lat, pickup.lon]);
    }
    if (destination && typeof destination.lat === 'number' && typeof destination.lon === 'number') {
      points.push([destination.lat, destination.lon]);
    }
    if (routeCoordinates && routeCoordinates.length > 0) {
      routeCoordinates.forEach(([lat, lon]) => points.push([lat, lon]));
    }

    if (points.length === 1) {
      map.setView(points[0], 15, { animate: true });
    } else if (points.length > 1) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16, animate: true });
    }
  }, [map, pickup, destination, routeCoordinates]);

  return null;
}

const createPickupIcon = () =>
  L.divIcon({
    className: 'custom-pickup-marker',
    html: '<div style="position: relative; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px;"><div style="position: absolute; width: 36px; height: 36px; border-radius: 50%; background: rgba(0, 201, 183, 0.25); animation: pulse-ring-anim 2s infinite;"></div><div style="position: absolute; width: 26px; height: 26px; border-radius: 50%; background: #00C9B7; border: 3px solid #FFFFFF; box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><span style="color: #FFFFFF; font-weight: 800; font-size: 13px; line-height: 1;">A</span></div></div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });

const createDestinationIcon = () =>
  L.divIcon({
    className: 'custom-destination-marker',
    html: '<div style="position: relative; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px;"><div style="position: absolute; width: 36px; height: 36px; border-radius: 50%; background: rgba(239, 68, 68, 0.25); animation: pulse-ring-anim 2s infinite;"></div><div style="position: absolute; width: 26px; height: 26px; border-radius: 50%; background: #EF4444; border: 3px solid #FFFFFF; box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><span style="color: #FFFFFF; font-weight: 800; font-size: 13px; line-height: 1;">B</span></div></div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });

const createDriverIcon = (heading = 0) =>
  L.divIcon({
    className: 'custom-driver-marker',
    html: `<div style="position: relative; display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; transform: rotate(${heading}deg);"><div style="position: absolute; width: 32px; height: 32px; border-radius: 50%; background: #0B0E11; border: 2.5px solid #00C9B7; box-shadow: 0 4px 12px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00C9B7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 19 21 12 17 5 21 12 2"/></svg></div></div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  });

export interface RideMapProps {
  pickup?: LocationResult | { lat: number; lon: number; name?: string; display_name?: string } | null;
  destination?: LocationResult | { lat: number; lon: number; name?: string; display_name?: string } | null;
  driverLocation?: { lat: number; lon: number; heading?: number } | null;
  route?: RouteResult | null;
  className?: string;
  defaultCenter?: [number, number];
  defaultZoom?: number;
  interactive?: boolean;
}

export const RideMap: React.FC<RideMapProps> = ({
  pickup,
  destination,
  driverLocation,
  route,
  className = 'h-full w-full',
  defaultCenter = [21.0285, 105.8542],
  defaultZoom = 13,
  interactive = true,
}) => {
  const pickupIcon = useMemo(() => createPickupIcon(), []);
  const destinationIcon = useMemo(() => createDestinationIcon(), []);
  const driverIcon = useMemo(() => createDriverIcon(driverLocation?.heading || 0), [driverLocation?.heading]);

  const polylinePositions = useMemo<[number, number][]>(() => {
    if (!route?.geometry?.coordinates) return [];
    return route.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
  }, [route?.geometry?.coordinates]);

  const center: [number, number] = useMemo(() => {
    if (pickup && typeof pickup.lat === 'number' && typeof pickup.lon === 'number') {
      return [pickup.lat, pickup.lon];
    }
    return defaultCenter;
  }, [pickup, defaultCenter]);

  return (
    <div className={`relative overflow-hidden rounded-2xl ${className}`}>
      <MapContainer
        center={center}
        zoom={defaultZoom}
        scrollWheelZoom={interactive}
        dragging={interactive}
        touchZoom={interactive}
        doubleClickZoom={interactive}
        zoomControl={interactive}
        className="h-full w-full z-0"
        style={{ minHeight: '260px' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        <MapBoundsUpdater
          pickup={pickup}
          destination={destination}
          routeCoordinates={polylinePositions}
        />

        {polylinePositions.length > 0 && (
          <>
            <Polyline
              positions={polylinePositions}
              pathOptions={{
                color: '#008F88',
                weight: 8,
                opacity: 0.35,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            <Polyline
              positions={polylinePositions}
              pathOptions={{
                color: '#00C9B7',
                weight: 5,
                opacity: 0.95,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          </>
        )}

        {pickup && typeof pickup.lat === 'number' && typeof pickup.lon === 'number' && (
          <Marker position={[pickup.lat, pickup.lon]} icon={pickupIcon}>
            <Popup className="custom-map-popup">
              <div className="text-xs font-semibold text-gray-900 dark:text-white">
                <span className="text-[#00C9B7] font-bold mr-1">[Điểm đón]</span>
                {pickup.name || ('display_name' in pickup ? pickup.display_name : 'Điểm đón của bạn')}
              </div>
            </Popup>
          </Marker>
        )}

        {destination && typeof destination.lat === 'number' && typeof destination.lon === 'number' && (
          <Marker position={[destination.lat, destination.lon]} icon={destinationIcon}>
            <Popup className="custom-map-popup">
              <div className="text-xs font-semibold text-gray-900 dark:text-white">
                <span className="text-red-500 font-bold mr-1">[Điểm đến]</span>
                {destination.name || ('display_name' in destination ? destination.display_name : 'Điểm đến')}
              </div>
            </Popup>
          </Marker>
        )}

        {driverLocation && typeof driverLocation.lat === 'number' && typeof driverLocation.lon === 'number' && (
          <Marker position={[driverLocation.lat, driverLocation.lon]} icon={driverIcon}>
            <Popup className="custom-map-popup">
              <div className="text-xs font-semibold text-gray-900 dark:text-white">
                <span className="text-[#00C9B7] font-bold mr-1">[Tài xế]</span>
                Đang di chuyển đến bạn
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {route && (
        <div className="absolute top-3 left-3 z-[1000] bg-white/90 dark:bg-gray-900/90 backdrop-blur-md px-3.5 py-2 rounded-xl shadow-lg border border-black/5 dark:border-white/10 flex items-center space-x-3 text-xs">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase font-bold tracking-wider">Khoảng cách</span>
            <span className="font-bold text-gray-900 dark:text-white text-sm">
              {route.distance_km ? `${route.distance_km} km` : `${((route.distance_meters || 0) / 1000).toFixed(1)} km`}
            </span>
          </div>
          <div className="w-px h-6 bg-gray-200 dark:bg-gray-700"></div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase font-bold tracking-wider">Thời gian dự kiến</span>
            <span className="font-bold text-[#00C9B7] text-sm">
              {route.duration_minutes ? `${route.duration_minutes} phút` : `${Math.max(1, Math.round((route.duration_seconds || 0) / 60))} phút`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
