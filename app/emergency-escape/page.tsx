'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { RiskBadge } from '@/components/ui/badge';
import { MapContainer, useMapInstance } from '@/components/map/MapContainer';
import { RouteRenderer } from '@/components/map/RouteRenderer';
import { MarkerLayer } from '@/components/map/MarkerLayer';
import { LegendPanel, RISK_LEGEND_ITEMS } from '@/components/map/LegendPanel';
import { useEmergencyEscapeMutation } from '@/hooks/useApi';
import { useAppStore } from '@/store/appStore';
import { formatDistance, formatTime, formatRiskScore, EMERGENCY_ICONS, EMERGENCY_LABELS, cn } from '@/lib/utils';
import { MapPin, Siren, Loader2, Sparkles } from 'lucide-react';
import type { EmergencyRoute } from '@/types';

export default function EmergencyEscapePage() {
  const { map, handleMapLoad } = useMapInstance();
  const { mapCenter, currentHour } = useAppStore();

  const [location, setLocation] = useState('');
  const [selectedRoute, setSelectedRoute] = useState<EmergencyRoute | null>(null);

  const mutation = useEmergencyEscapeMutation();
  const data = mutation.data;

  const handleGenerate = () => {
    if (!location) return;
    mutation.mutate({ location, hour: currentHour });
    setSelectedRoute(null);
  };

  const routes = data?.routes ?? [];
  const activeRoute = selectedRoute ?? routes[0] ?? null;

  const routesForRenderer = activeRoute
    ? [
        {
          route_id: `emergency-${activeRoute.destination_type}`,
          label: EMERGENCY_LABELS[activeRoute.destination_type],
          distance_km: activeRoute.distance_km,
          travel_time_min: activeRoute.travel_time_min,
          avg_risk: activeRoute.risk_score,
          max_risk: activeRoute.risk_score,
          confidence_score: 1,
          safety_profile: 'emergency',
          explanation: '',
          coordinates: activeRoute.coordinates,
          segments: [],
          risk_label: activeRoute.risk_label,
        },
      ]
    : [];

  const markers = [];
  if (activeRoute) {
    markers.push({
      coordinate: activeRoute.coordinates[0],
      color: '#00E676',
      label: 'Your Location',
      icon: '●',
    });
    markers.push({
      coordinate: activeRoute.destination_coordinates,
      color: '#FF5252',
      label: activeRoute.destination_name,
      icon: EMERGENCY_ICONS[activeRoute.destination_type],
    });
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-danger/10 border border-danger/20 flex items-center justify-center">
            <Siren size={20} className="text-danger" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Emergency Escape Routing</h1>
            <p className="text-slate-400 text-sm">
              Instant routes to nearest police, hospital, metro, and safe public areas
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Emergency Routing Dashboard</CardTitle>
            <CardDescription>Enter your current location to find the nearest safe destinations</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-danger" />
                <Input
                  placeholder="Enter your current location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Button onClick={handleGenerate} disabled={!location || mutation.isPending} size="lg" variant="danger">
                {mutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Locating...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Find Escape Routes
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {mutation.isError && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to find emergency routes. Please check the backend connection and try again.
            </p>
          </Card>
        )}

        {routes.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
            {/* Left - route cards */}
            <div className="space-y-3 order-2 lg:order-1 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
              {routes.map((route) => {
                const isSelected = activeRoute?.destination_type === route.destination_type;
                return (
                  <Card
                    key={route.destination_type}
                    onClick={() => setSelectedRoute(route)}
                    className={cn(
                      'p-4 cursor-pointer transition-all',
                      isSelected ? 'border-danger/40 glow-border bg-danger/5' : 'hover:border-white/10'
                    )}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center text-xl">
                          {EMERGENCY_ICONS[route.destination_type]}
                        </div>
                        <div>
                          <div className="font-display font-semibold text-white text-sm">
                            {EMERGENCY_LABELS[route.destination_type]}
                          </div>
                          <div className="text-xs text-slate-500 truncate max-w-[180px]">
                            {route.destination_name}
                          </div>
                        </div>
                      </div>
                      <RiskBadge label={route.risk_label} />
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-sm font-bold text-white">{formatDistance(route.distance_km)}</div>
                        <div className="text-xs text-slate-500">Distance</div>
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white">{formatTime(route.travel_time_min)}</div>
                        <div className="text-xs text-slate-500">Time</div>
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white">{formatRiskScore(route.risk_score)}</div>
                        <div className="text-xs text-slate-500">Risk</div>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>

            {/* Right - map */}
            <div className="order-1 lg:order-2 relative">
              <MapContainer center={mapCenter} zoom={13} onMapLoad={handleMapLoad} className="h-[500px] lg:h-[calc(100vh-280px)]" />
              {activeRoute && (
                <>
                  <RouteRenderer map={map} routes={routesForRenderer} />
                  <MarkerLayer map={map} markers={markers} />
                  <LegendPanel items={RISK_LEGEND_ITEMS} />
                </>
              )}
            </div>
          </div>
        )}

        {routes.length === 0 && !mutation.isPending && !mutation.isError && (
          <Card className="p-12 text-center">
            <Siren size={40} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              Enter your current location above to instantly generate emergency escape routes to
              the nearest police station, hospital, metro station, public area, and CCTV-dense zone.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
