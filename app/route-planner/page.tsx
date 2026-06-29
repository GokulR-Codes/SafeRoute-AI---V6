'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { MapContainer, useMapInstance } from '@/components/map/MapContainer';
import { RouteRenderer } from '@/components/map/RouteRenderer';
import { MarkerLayer, SourceMarkerConfig, DestinationMarkerConfig } from '@/components/map/MarkerLayer';
import { LegendPanel, RISK_LEGEND_ITEMS } from '@/components/map/LegendPanel';
import { RouteComparisonPanel } from '@/components/route/RouteComparisonPanel';
import { useRecommendRoutes } from '@/hooks/useApi';
import { useAppStore } from '@/store/appStore';
import { formatHour } from '@/lib/utils';
import { MapPin, Navigation, Sparkles, Loader2 } from 'lucide-react';
import type { RouteRequest, RouteRecommendation } from '@/types';

export default function RoutePlannerPage() {
  const { map, handleMapLoad } = useMapInstance();
  const { currentHour, setCurrentHour, mapCenter } = useAppStore();

  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [profile, setProfile] = useState<'safest' | 'fastest' | 'balanced'>('safest');
  const [hour, setHour] = useState(currentHour);
  const [request, setRequest] = useState<RouteRequest | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<RouteRecommendation | null>(null);

  const { data, isLoading, isFetching, error } = useRecommendRoutes(request);

  const handleGenerate = () => {
    if (!source || !destination) return;
    const req: RouteRequest = { source, destination, hour, profile };
    setRequest(req);
    setCurrentHour(hour);
    setSelectedRoute(null);
  };

  const routes = data?.routes ?? [];

  const sourceCoord = routes[0]?.coordinates[0];
  const destCoord = routes[0]?.coordinates[routes[0]?.coordinates.length - 1];

  const markers = [];
  if (sourceCoord) markers.push(SourceMarkerConfig(sourceCoord));
  if (destCoord) markers.push(DestinationMarkerConfig(destCoord));

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="font-display font-bold text-2xl text-white mb-1">Route Planner</h1>
          <p className="text-slate-400 text-sm">
            Generate AI-recommended routes optimized for safety, speed, or balance
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
          {/* Left panel - Form & results */}
          <div className="space-y-6 order-2 lg:order-1">
            <Card>
              <CardHeader>
                <CardTitle>Plan Your Route</CardTitle>
                <CardDescription>Enter source and destination to generate routes</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Source Location</Label>
                  <div className="relative">
                    <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
                    <Input
                      placeholder="Enter starting point"
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div>
                  <Label>Destination</Label>
                  <div className="relative">
                    <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-danger" />
                    <Input
                      placeholder="Enter destination"
                      value={destination}
                      onChange={(e) => setDestination(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div>
                  <Label>Routing Profile</Label>
                  <Select value={profile} onValueChange={(v: any) => setProfile(v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="safest">Safest</SelectItem>
                      <SelectItem value="fastest">Fastest</SelectItem>
                      <SelectItem value="balanced">Balanced</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <Label className="mb-0">Departure Hour</Label>
                    <span className="text-xs font-mono text-primary">{formatHour(hour)}</span>
                  </div>
                  <Slider
                    value={[hour]}
                    onValueChange={([v]) => setHour(v)}
                    min={0}
                    max={23}
                    step={1}
                  />
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={!source || !destination || isFetching}
                  className="w-full"
                  size="lg"
                >
                  {isFetching ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Generating Routes...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      Generate Route
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {error && (
              <Card className="p-4 border-danger/30 bg-danger/5">
                <p className="text-danger text-sm">
                  Failed to generate routes. Please check the backend connection and try again.
                </p>
              </Card>
            )}

            {routes.length > 0 && (
              <div>
                <h3 className="font-display font-semibold text-white text-sm mb-3 px-1">
                  Route Recommendations
                </h3>
                <RouteComparisonPanel
                  routes={routes}
                  selectedRouteId={selectedRoute?.route_id ?? routes[0]?.route_id ?? null}
                  onSelectRoute={setSelectedRoute}
                />
              </div>
            )}

            {!isLoading && routes.length === 0 && !error && (
              <Card className="p-8 text-center">
                <Navigation size={32} className="text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">
                  Enter source and destination, then click Generate Route to see AI-recommended paths.
                </p>
              </Card>
            )}
          </div>

          {/* Right panel - Map */}
          <div className="order-1 lg:order-2 relative">
            <MapContainer center={mapCenter} zoom={12} onMapLoad={handleMapLoad} className="h-[500px] lg:h-[calc(100vh-200px)]" />
            {routes.length > 0 && (
              <>
                <RouteRenderer
                  map={map}
                  routes={routes}
                  selectedRouteId={selectedRoute?.route_id ?? routes[0]?.route_id ?? null}
                  onRouteClick={setSelectedRoute}
                />
                <MarkerLayer map={map} markers={markers} />
                <LegendPanel items={RISK_LEGEND_ITEMS} />
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
