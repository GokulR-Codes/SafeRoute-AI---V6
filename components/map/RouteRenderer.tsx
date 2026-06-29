'use client';

import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import type { RouteRecommendation, RouteCoordinate } from '@/types';
import { getRiskColor } from '@/lib/utils';

interface RouteRendererProps {
  map: mapboxgl.Map | null;
  routes: RouteRecommendation[];
  selectedRouteId?: string | null;
  onRouteClick?: (route: RouteRecommendation) => void;
}

// Renders one or more routes as colored line layers, animated dash for selected route
export function RouteRenderer({ map, routes, selectedRouteId, onRouteClick }: RouteRendererProps) {
  const layerIdsRef = useRef<string[]>([]);

  useEffect(() => {
    if (!map) return;

    const cleanup = () => {
      layerIdsRef.current.forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      });
      layerIdsRef.current = [];
    };

    cleanup();

    routes.forEach((route, idx) => {
      const sourceId = `route-${route.route_id}`;
      const isSelected = selectedRouteId ? route.route_id === selectedRouteId : idx === 0;

      const coordinates = route.coordinates.map((c) => [c.lng, c.lat]);

      // Build risk-colored segments if per-coordinate risk available
      const features = [];
      for (let i = 0; i < coordinates.length - 1; i++) {
        const c1 = route.coordinates[i];
        const c2 = route.coordinates[i + 1];
        const segmentRisk = ((c1.risk ?? route.avg_risk) + (c2.risk ?? route.avg_risk)) / 2;
        features.push({
          type: 'Feature' as const,
          properties: { risk: segmentRisk },
          geometry: {
            type: 'LineString' as const,
            coordinates: [coordinates[i], coordinates[i + 1]],
          },
        });
      }

      if (!map.getSource(sourceId)) {
        map.addSource(sourceId, {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features,
          },
        });

        map.addLayer({
          id: sourceId,
          type: 'line',
          source: sourceId,
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color': [
              'interpolate',
              ['linear'],
              ['get', 'risk'],
              0, '#00E676',
              0.5, '#FFC107',
              0.75, '#FF9800',
              1, '#FF5252',
            ],
            'line-width': isSelected ? 5 : 3,
            'line-opacity': isSelected ? 1 : 0.4,
          },
        });

        if (onRouteClick) {
          map.on('click', sourceId, () => onRouteClick(route));
          map.on('mouseenter', sourceId, () => {
            map.getCanvas().style.cursor = 'pointer';
          });
          map.on('mouseleave', sourceId, () => {
            map.getCanvas().style.cursor = '';
          });
        }

        layerIdsRef.current.push(sourceId);
      }
    });

    // Fit bounds to first route
    if (routes.length > 0 && routes[0].coordinates.length > 0) {
      const coords = routes[0].coordinates.map((c) => [c.lng, c.lat] as [number, number]);
      const bounds = new mapboxgl.LngLatBounds(coords[0], coords[0]);
      coords.forEach((coord) => bounds.extend(coord));
      map.fitBounds(bounds, { padding: 60, duration: 800 });
    }

    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, routes, selectedRouteId]);

  return null;
}

export function getRouteSegmentColor(risk: number) {
  return getRiskColor(risk);
}
