'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MapContainer, useMapInstance } from '@/components/map/MapContainer';
import { ZoneLayer } from '@/components/map/ZoneLayer';
import { useDangerZones } from '@/hooks/useApi';
import { useAppStore } from '@/store/appStore';
import { formatRiskScore, cn } from '@/lib/utils';
import { ShieldAlert, MapPin, Layers } from 'lucide-react';
import type { Zone } from '@/types';

export default function DangerZonesPage() {
  const { map, handleMapLoad } = useMapInstance();
  const { mapCenter } = useAppStore();
  const { data, isLoading, error } = useDangerZones();
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);

  const zones = data?.zones ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-danger/10 border border-danger/20 flex items-center justify-center">
            <ShieldAlert size={20} className="text-danger" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Danger Zones</h1>
            <p className="text-slate-400 text-sm">
              Clusters of high-risk areas identified by the temporal risk graph engine
            </p>
          </div>
        </div>

        {error && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to load danger zones. Please check the backend connection.
            </p>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
          {/* Zone cards */}
          <div className="space-y-3 order-2 lg:order-1 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
            <div className="flex items-center justify-between px-1 mb-2">
              <span className="text-sm font-semibold text-white flex items-center gap-2">
                <Layers size={14} />
                {isLoading ? 'Loading zones...' : `${zones.length} Danger Zones`}
              </span>
            </div>

            {isLoading &&
              Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 skeleton rounded-xl" />)}

            {zones.map((zone) => (
              <Card
                key={zone.zone_id}
                onClick={() => setSelectedZone(zone)}
                className={cn(
                  'p-4 cursor-pointer transition-all',
                  selectedZone?.zone_id === zone.zone_id
                    ? 'border-danger/40 glow-border bg-danger/5'
                    : 'hover:border-white/10'
                )}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-danger/10 flex items-center justify-center">
                      <ShieldAlert size={16} className="text-danger" />
                    </div>
                    <div>
                      <div className="font-display font-semibold text-white text-sm">{zone.zone_name}</div>
                      <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <MapPin size={10} />
                        {zone.centroid.lat.toFixed(4)}, {zone.centroid.lng.toFixed(4)}
                      </div>
                    </div>
                  </div>
                  <Badge variant="unsafe">Danger</Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="text-center p-2 rounded-lg bg-surface">
                    <div className="text-sm font-bold text-white">{zone.node_count}</div>
                    <div className="text-xs text-slate-500">Node Count</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-surface">
                    <div className="text-sm font-bold text-white">{formatRiskScore(zone.risk_score)}</div>
                    <div className="text-xs text-slate-500">Risk Score</div>
                  </div>
                </div>
              </Card>
            ))}

            {!isLoading && zones.length === 0 && !error && (
              <Card className="p-8 text-center">
                <p className="text-slate-400 text-sm">No danger zones found.</p>
              </Card>
            )}
          </div>

          {/* Map */}
          <div className="order-1 lg:order-2 relative">
            <MapContainer
              center={selectedZone ? selectedZone.centroid : mapCenter}
              zoom={selectedZone ? 14 : 11}
              onMapLoad={handleMapLoad}
              className="h-[500px] lg:h-[calc(100vh-220px)]"
            />
            {zones.length > 0 && <ZoneLayer map={map} zones={zones} type="danger" />}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
