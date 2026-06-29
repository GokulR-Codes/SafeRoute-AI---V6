'use client';

import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import type { Coordinate } from '@/types';

interface MarkerConfig {
  coordinate: Coordinate;
  color?: string;
  label?: string;
  icon?: string;
}

interface MarkerLayerProps {
  map: mapboxgl.Map | null;
  markers: MarkerConfig[];
}

export function MarkerLayer({ map, markers }: MarkerLayerProps) {
  const markerRefs = useRef<mapboxgl.Marker[]>([]);

  useEffect(() => {
    if (!map) return;

    // Clear existing markers
    markerRefs.current.forEach((m) => m.remove());
    markerRefs.current = [];

    markers.forEach(({ coordinate, color = '#00E676', label, icon }) => {
      const el = document.createElement('div');
      el.style.width = '32px';
      el.style.height = '32px';
      el.style.borderRadius = '50%';
      el.style.background = color;
      el.style.border = '3px solid #0A0F1F';
      el.style.boxShadow = `0 0 12px ${color}80`;
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.fontSize = '14px';
      el.style.cursor = 'pointer';
      if (icon) el.textContent = icon;

      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([coordinate.lng, coordinate.lat])
        .addTo(map);

      if (label) {
        marker.setPopup(
          new mapboxgl.Popup({ offset: 20, closeButton: false }).setHTML(
            `<div style="font-family: Inter, sans-serif; font-size: 12px; color: #0A0F1F; font-weight: 600;">${label}</div>`
          )
        );
      }

      markerRefs.current.push(marker);
    });

    return () => {
      markerRefs.current.forEach((m) => m.remove());
      markerRefs.current = [];
    };
  }, [map, markers]);

  return null;
}

export const SourceMarkerConfig = (coordinate: Coordinate): MarkerConfig => ({
  coordinate,
  color: '#00E676',
  label: 'Source',
  icon: 'A',
});

export const DestinationMarkerConfig = (coordinate: Coordinate): MarkerConfig => ({
  coordinate,
  color: '#FF5252',
  label: 'Destination',
  icon: 'B',
});
