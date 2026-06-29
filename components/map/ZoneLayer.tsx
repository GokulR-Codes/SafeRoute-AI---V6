'use client';

import { useEffect } from 'react';
import type mapboxgl from 'mapbox-gl';
import type { Zone } from '@/types';

interface ZoneLayerProps {
  map: mapboxgl.Map | null;
  zones: Zone[];
  type: 'safe' | 'danger';
}

export function ZoneLayer({ map, zones, type }: ZoneLayerProps) {
  const sourceId = `${type}-zones-source`;
  const layerId = `${type}-zones-layer`;
  const outlineId = `${type}-zones-outline`;
  const color = type === 'safe' ? '#00E676' : '#FF5252';

  useEffect(() => {
    if (!map) return;

    const data = {
      type: 'FeatureCollection' as const,
      features: zones.map((z) => ({
        type: 'Feature' as const,
        properties: { name: z.zone_name, risk: z.risk_score, nodes: z.node_count },
        geometry: {
          type: 'Point' as const,
          coordinates: [z.centroid.lng, z.centroid.lat],
        },
      })),
    };

    if (map.getSource(sourceId)) {
      (map.getSource(sourceId) as mapboxgl.GeoJSONSource).setData(data);
      return;
    }

    map.addSource(sourceId, { type: 'geojson', data });

    map.addLayer({
      id: layerId,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'nodes'], 0, 8, 100, 30],
        'circle-color': color,
        'circle-opacity': 0.2,
      },
    });

    map.addLayer({
      id: outlineId,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'nodes'], 0, 8, 100, 30],
        'circle-color': 'transparent',
        'circle-stroke-color': color,
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.8,
      },
    });

    return () => {
      if (map.getLayer(outlineId)) map.removeLayer(outlineId);
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, zones, type]);

  return null;
}
