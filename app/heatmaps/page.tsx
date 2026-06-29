'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { MapContainer, useMapInstance } from '@/components/map/MapContainer';
import { HeatmapLayer } from '@/components/map/HeatmapLayer';
import { ZoneLayer } from '@/components/map/ZoneLayer';
import { LegendPanel, RISK_LEGEND_ITEMS } from '@/components/map/LegendPanel';
import { useHeatmap } from '@/hooks/useApi';
import { useAppStore } from '@/store/appStore';
import { formatHour, getTimeOfDayIcon } from '@/lib/utils';
import { Flame, Filter, ShieldHalf, ShieldAlert } from 'lucide-react';

export default function HeatmapPage() {
  const { map, handleMapLoad } = useMapInstance();
  const { mapCenter } = useAppStore();

  const [hour, setHour] = useState<number | undefined>(undefined);
  const [showSafeZones, setShowSafeZones] = useState(true);
  const [showDangerZones, setShowDangerZones] = useState(true);

  const { data, isLoading, error } = useHeatmap(hour);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
            <Flame size={20} className="text-orange-400" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Risk Heatmap</h1>
            <p className="text-slate-400 text-sm">
              City-wide risk distribution with safe and danger zone overlays
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
          {/* Controls */}
          <div className="space-y-6 order-2 lg:order-1">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Filter size={16} />
                  Hour Filter
                </CardTitle>
                <CardDescription>Filter heatmap by hour of day</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <Label className="mb-0">Selected Hour</Label>
                    <span className="text-xs font-mono text-primary">
                      {hour !== undefined ? `${formatHour(hour)} ${getTimeOfDayIcon(hour)}` : 'All Hours'}
                    </span>
                  </div>
                  <Slider
                    value={[hour ?? 12]}
                    onValueChange={([v]) => setHour(v)}
                    min={0}
                    max={23}
                    step={1}
                  />
                </div>
                <Button variant="outline" size="sm" onClick={() => setHour(undefined)} className="w-full">
                  Show All Hours
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Overlays</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <button
                  onClick={() => setShowSafeZones((s) => !s)}
                  className="w-full flex items-center justify-between p-3 rounded-lg bg-surface border border-border hover:border-primary/30 transition-colors"
                >
                  <div className="flex items-center gap-2 text-sm text-slate-200">
                    <ShieldHalf size={16} className="text-primary" />
                    Safe Zones Overlay
                  </div>
                  <div className={`w-8 h-4 rounded-full transition-colors ${showSafeZones ? 'bg-primary' : 'bg-muted'} relative`}>
                    <div
                      className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                        showSafeZones ? 'translate-x-4' : 'translate-x-0.5'
                      }`}
                    />
                  </div>
                </button>

                <button
                  onClick={() => setShowDangerZones((s) => !s)}
                  className="w-full flex items-center justify-between p-3 rounded-lg bg-surface border border-border hover:border-danger/30 transition-colors"
                >
                  <div className="flex items-center gap-2 text-sm text-slate-200">
                    <ShieldAlert size={16} className="text-danger" />
                    Danger Zones Overlay
                  </div>
                  <div className={`w-8 h-4 rounded-full transition-colors ${showDangerZones ? 'bg-danger' : 'bg-muted'} relative`}>
                    <div
                      className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                        showDangerZones ? 'translate-x-4' : 'translate-x-0.5'
                      }`}
                    />
                  </div>
                </button>
              </CardContent>
            </Card>

            {error && (
              <Card className="p-4 border-danger/30 bg-danger/5">
                <p className="text-danger text-sm">
                  Failed to load heatmap data. Please check the backend connection.
                </p>
              </Card>
            )}

            {data && (
              <Card className="p-4">
                <div className="text-xs text-slate-400 mb-1">Total Risk Points</div>
                <div className="font-display font-bold text-xl text-white">{data.points.length.toLocaleString()}</div>
              </Card>
            )}
          </div>

          {/* Map */}
          <div className="order-1 lg:order-2 relative">
            <MapContainer
              center={mapCenter}
              zoom={11}
              onMapLoad={handleMapLoad}
              className="h-[500px] lg:h-[calc(100vh-200px)]"
            />
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-surface/50 rounded-xl">
                <div className="skeleton w-32 h-8 rounded-lg" />
              </div>
            )}
            {data && (
              <>
                <HeatmapLayer map={map} points={data.points} />
                {showSafeZones && <ZoneLayer map={map} zones={data.safe_zones} type="safe" />}
                {showDangerZones && <ZoneLayer map={map} zones={data.danger_zones} type="danger" />}
                <LegendPanel items={RISK_LEGEND_ITEMS} />
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
