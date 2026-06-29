'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { RiskBadge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { MapContainer, useMapInstance } from '@/components/map/MapContainer';
import { RouteRenderer } from '@/components/map/RouteRenderer';
import { MarkerLayer, SourceMarkerConfig, DestinationMarkerConfig } from '@/components/map/MarkerLayer';
import { LegendPanel, RISK_LEGEND_ITEMS } from '@/components/map/LegendPanel';
import { SafetyGauge } from '@/components/features/SafetyGauge';
import { useWomenSafetyMutation } from '@/hooks/useApi';
import { useAppStore } from '@/store/appStore';
import { formatHour, formatDistance, formatTime, formatRiskScore } from '@/lib/utils';
import { MapPin, ShieldCheck, Loader2, Lightbulb, Users, Sparkles } from 'lucide-react';

export default function WomenSafetyPage() {
  const { map, handleMapLoad } = useMapInstance();
  const { currentHour, mapCenter } = useAppStore();

  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [hour, setHour] = useState(currentHour);

  const mutation = useWomenSafetyMutation();
  const data = mutation.data;

  const handleGenerate = () => {
    if (!source || !destination) return;
    mutation.mutate({ source, destination, hour });
  };

  const sourceCoord = data?.coordinates[0];
  const destCoord = data?.coordinates[data.coordinates.length - 1];
  const markers = [];
  if (sourceCoord) markers.push(SourceMarkerConfig(sourceCoord));
  if (destCoord) markers.push(DestinationMarkerConfig(destCoord));

  const routeForRenderer = data
    ? [
        {
          route_id: 'women-safe-route',
          label: 'Women Safe Route',
          distance_km: data.distance_km,
          travel_time_min: data.travel_time_min,
          avg_risk: data.avg_risk,
          max_risk: data.avg_risk,
          confidence_score: data.women_safety_score,
          safety_profile: 'women-safe',
          explanation: data.safety_explanation,
          coordinates: data.coordinates,
          segments: [],
          risk_label: data.risk_label,
        },
      ]
    : [];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-pink-500/10 border border-pink-500/20 flex items-center justify-center">
            <ShieldCheck size={20} className="text-pink-400" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Women Safety Routing</h1>
            <p className="text-slate-400 text-sm">
              Routes optimized for lighting, isolation, and women's safety scoring
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
          {/* Left panel */}
          <div className="space-y-6 order-2 lg:order-1">
            <Card>
              <CardHeader>
                <CardTitle>Generate Women Safe Route</CardTitle>
                <CardDescription>Optimized for lighting and isolation safety factors</CardDescription>
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
                  <div className="flex items-center justify-between mb-1.5">
                    <Label className="mb-0">Departure Hour</Label>
                    <span className="text-xs font-mono text-primary">{formatHour(hour)}</span>
                  </div>
                  <Slider value={[hour]} onValueChange={([v]) => setHour(v)} min={0} max={23} step={1} />
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={!source || !destination || mutation.isPending}
                  className="w-full"
                  size="lg"
                >
                  {mutation.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Analyzing Safety...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      Generate Women Safe Route
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {mutation.isError && (
              <Card className="p-4 border-danger/30 bg-danger/5">
                <p className="text-danger text-sm">
                  Failed to generate route. Please check the backend connection and try again.
                </p>
              </Card>
            )}

            {data && (
              <>
                <Card className="p-6 flex flex-col items-center">
                  <SafetyGauge score={data.women_safety_score} label="Women Safety Score" size={180} />
                  <div className="flex justify-center mt-2">
                    <RiskBadge label={data.risk_label} />
                  </div>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Route Summary</CardTitle>
                  </CardHeader>
                  <CardContent className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <div className="text-lg font-display font-bold text-white">
                        {formatDistance(data.distance_km)}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Distance</div>
                    </div>
                    <div>
                      <div className="text-lg font-display font-bold text-white">
                        {formatTime(data.travel_time_min)}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Travel Time</div>
                    </div>
                    <div>
                      <div className="text-lg font-display font-bold text-white">
                        {formatRiskScore(data.avg_risk)}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Avg Risk</div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Lightbulb size={16} className="text-warning" />
                      Lighting Analysis
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Score</span>
                      <span className="text-white font-medium">{formatRiskScore(data.lighting_analysis.score)}</span>
                    </div>
                    <Progress value={data.lighting_analysis.score * 100} indicatorColor="#FFC107" />
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Label</span>
                      <span className="text-white font-medium">{data.lighting_analysis.label}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <div className="text-center p-2 rounded-lg bg-surface">
                        <div className="text-sm font-bold text-primary">
                          {data.lighting_analysis.well_lit_segments}
                        </div>
                        <div className="text-xs text-slate-500">Well-lit segments</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-surface">
                        <div className="text-sm font-bold text-danger">
                          {data.lighting_analysis.dark_segments}
                        </div>
                        <div className="text-xs text-slate-500">Dark segments</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Users size={16} className="text-secondary" />
                      Isolation Analysis
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Score</span>
                      <span className="text-white font-medium">{formatRiskScore(data.isolation_analysis.score)}</span>
                    </div>
                    <Progress value={data.isolation_analysis.score * 100} indicatorColor="#00BFA5" />
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Label</span>
                      <span className="text-white font-medium">{data.isolation_analysis.label}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <div className="text-center p-2 rounded-lg bg-surface">
                        <div className="text-sm font-bold text-primary">
                          {data.isolation_analysis.populated_segments}
                        </div>
                        <div className="text-xs text-slate-500">Populated segments</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-surface">
                        <div className="text-sm font-bold text-danger">
                          {data.isolation_analysis.isolated_segments}
                        </div>
                        <div className="text-xs text-slate-500">Isolated segments</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Safety Explanation</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-slate-400 leading-relaxed">{data.safety_explanation}</p>
                  </CardContent>
                </Card>
              </>
            )}

            {!data && !mutation.isPending && !mutation.isError && (
              <Card className="p-8 text-center">
                <ShieldCheck size={32} className="text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">
                  Enter source and destination to generate a women-safety-optimized route with full
                  lighting and isolation analysis.
                </p>
              </Card>
            )}
          </div>

          {/* Right - Map */}
          <div className="order-1 lg:order-2 relative">
            <MapContainer center={mapCenter} zoom={12} onMapLoad={handleMapLoad} className="h-[500px] lg:h-[calc(100vh-200px)]" />
            {data && (
              <>
                <RouteRenderer map={map} routes={routeForRenderer} />
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
