'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { cn } from '@/lib/utils';
import type { Coordinate } from '@/types';

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '';

interface MapContainerProps {
  center?: Coordinate;
  zoom?: number;
  className?: string;
  onMapLoad?: (map: mapboxgl.Map) => void;
  children?: React.ReactNode;
}

export function MapContainer({
  center = { lat: 28.6139, lng: 77.209 },
  zoom = 12,
  className,
  onMapLoad,
}: MapContainerProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [tokenMissing, setTokenMissing] = useState(false);

  useEffect(() => {
    if (!mapboxgl.accessToken) {
      setTokenMissing(true);
      return;
    }

    if (!mapContainerRef.current || mapRef.current) return;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [center.lng, center.lat],
      zoom,
      attributionControl: false,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'top-right');

    map.on('load', () => {
      setMapLoaded(true);
      onMapLoad?.(map);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update center/zoom when changed
  useEffect(() => {
    if (mapRef.current && mapLoaded) {
      mapRef.current.flyTo({ center: [center.lng, center.lat], zoom, duration: 1000 });
    }
  }, [center.lat, center.lng, zoom, mapLoaded]);

  if (tokenMissing) {
    return (
      <div className={cn('rounded-xl border border-border bg-surface flex items-center justify-center', className)}>
        <div className="text-center p-8">
          <p className="text-slate-400 text-sm mb-2">Mapbox token not configured</p>
          <p className="text-slate-500 text-xs">
            Set NEXT_PUBLIC_MAPBOX_TOKEN in your environment variables
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('relative rounded-xl overflow-hidden border border-border', className)}>
      <div ref={mapContainerRef} className="w-full h-full" />
      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface skeleton" />
      )}
    </div>
  );
}

export function useMapInstance() {
  const [map, setMap] = useState<mapboxgl.Map | null>(null);
  const handleMapLoad = useCallback((m: mapboxgl.Map) => setMap(m), []);
  return { map, handleMapLoad };
}

export { mapboxgl };
