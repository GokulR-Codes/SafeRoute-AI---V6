'use client';

import { useEffect, useRef } from 'react';
import type mapboxgl from 'mapbox-gl';
import type { HeatmapPoint } from '@/types';

interface HeatmapLayerProps {
  map: mapboxgl.Map | null;
  points: HeatmapPoint[];
}

export function HeatmapLayer({ map, points }: HeatmapLayerProps) {
  const sourceId = 'risk-heatmap-source';
  const layerId = 'risk-heatmap-layer';
  const initialized = useRef(false);

  useEffect(() => {
    if (!map) return;

    const data = {
      type: 'FeatureCollection' as const,
      features: points.map((p) => ({
        type: 'Feature' as const,
        properties: { intensity: p.intensity, risk: p.risk_score },
        geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
      })),
    };

    if (map.getSource(sourceId)) {
      (map.getSource(sourceId) as mapboxgl.GeoJSONSource).setData(data);
      return;
    }

    map.addSource(sourceId, { type: 'geojson', data });

    map.addLayer({
      id: layerId,
      type: 'heatmap',
      source: sourceId,
      maxzoom: 18,
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'risk'], 0, 0, 1, 1],
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 18, 3],
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0, 'rgba(0, 230, 118, 0)',
          0.2, 'rgba(0, 230, 118, 0.5)',
          0.4, 'rgba(255, 193, 7, 0.6)',
          0.6, 'rgba(255, 152, 0, 0.7)',
          0.8, 'rgba(255, 82, 82, 0.8)',
          1, 'rgba(255, 82, 82, 1)',
        ],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 4, 18, 30],
        'heatmap-opacity': 0.75,
      },
    });

    initialized.current = true;

    return () => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      initialized.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, points]);

  return null;
}
