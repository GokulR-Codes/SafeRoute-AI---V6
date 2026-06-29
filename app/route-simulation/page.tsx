'use client';

import { useState, useEffect, useRef } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { RiskBadge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useRouteSimulation } from '@/hooks/useApi';
import { formatDistance, formatRiskScore, cn } from '@/lib/utils';
import { PlaySquare, Pause, Play, RotateCcw, MapPin, Car, Construction } from 'lucide-react';
import type { SimulationSegment } from '@/types';

export default function RouteSimulationPage() {
  const [routeId, setRouteId] = useState('');
  const [activeRouteId, setActiveRouteId] = useState<string | null>(null);
  const [currentSegment, setCurrentSegment] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const { data, isLoading, error } = useRouteSimulation(activeRouteId);

  const segments = data?.segments ?? [];

  useEffect(() => {
    if (isPlaying && segments.length > 0) {
      intervalRef.current = setInterval(() => {
        setCurrentSegment((prev) => {
          if (prev >= segments.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, segments.length]);

  const handleLoad = () => {
    if (!routeId) return;
    setActiveRouteId(routeId);
    setCurrentSegment(0);
    setIsPlaying(false);
  };

  const handleReset = () => {
    setCurrentSegment(0);
    setIsPlaying(false);
  };

  const progress = segments.length > 0 ? ((currentSegment + 1) / segments.length) * 100 : 0;
  const activeSeg = segments[currentSegment];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <PlaySquare size={20} className="text-blue-400" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Route Simulation</h1>
            <p className="text-slate-400 text-sm">
              Minute-by-minute simulation of your journey with per-segment risk data
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Load Route Simulation</CardTitle>
            <CardDescription>Enter a route ID from a previously generated route</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                placeholder="Enter route ID (e.g. route-a-12345)"
                value={routeId}
                onChange={(e) => setRouteId(e.target.value)}
                className="flex-1"
              />
              <Button onClick={handleLoad} disabled={!routeId} size="lg">
                <PlaySquare size={16} />
                Load Simulation
              </Button>
            </div>
          </CardContent>
        </Card>

        {error && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to load route simulation. Please verify the route ID and backend connection.
            </p>
          </Card>
        )}

        {isLoading && (
          <Card className="p-12 text-center">
            <div className="skeleton h-4 w-1/2 mx-auto rounded-full mb-4" />
            <div className="skeleton h-4 w-1/3 mx-auto rounded-full" />
          </Card>
        )}

        {data && segments.length > 0 && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Total Time</div>
                <div className="font-display font-bold text-2xl text-white">{data.total_time_min} min</div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Total Distance</div>
                <div className="font-display font-bold text-2xl text-white">{formatDistance(data.total_distance_km)}</div>
              </Card>
            </div>

            {/* Simulation progress UI */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Simulation Progress</CardTitle>
                    <CardDescription>
                      Segment {currentSegment + 1} of {segments.length}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={handleReset}>
                      <RotateCcw size={14} />
                    </Button>
                    <Button size="sm" onClick={() => setIsPlaying((p) => !p)}>
                      {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                      {isPlaying ? 'Pause' : 'Play'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Progress value={progress} indicatorColor="#2196F3" />

                {/* Timeline visualization */}
                <div className="flex gap-1 overflow-x-auto pb-2">
                  {segments.map((seg, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setCurrentSegment(idx);
                        setIsPlaying(false);
                      }}
                      className={cn(
                        'flex-shrink-0 w-3 h-8 rounded-full transition-all',
                        idx === currentSegment ? 'ring-2 ring-white scale-110' : 'opacity-60 hover:opacity-100'
                      )}
                      style={{
                        backgroundColor:
                          seg.risk_label === 'safe'
                            ? '#00E676'
                            : seg.risk_label === 'moderate'
                            ? '#FFC107'
                            : seg.risk_label === 'caution'
                            ? '#FF9800'
                            : '#FF5252',
                      }}
                      title={`${seg.road_name} — Minute ${seg.minute}`}
                    />
                  ))}
                </div>

                {/* Active segment detail */}
                {activeSeg && (
                  <Card className="p-5 bg-surface border-border">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                          <Car size={18} className="text-blue-400" />
                        </div>
                        <div>
                          <div className="font-display font-semibold text-white">{activeSeg.road_name}</div>
                          <div className="text-xs text-slate-500">{activeSeg.road_type}</div>
                        </div>
                      </div>
                      <RiskBadge label={activeSeg.risk_label} />
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="text-center p-3 rounded-lg bg-card">
                        <div className="text-sm font-bold text-white">Minute {activeSeg.minute}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Timestamp</div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-card">
                        <div className="text-sm font-bold text-white">{formatDistance(activeSeg.distance_km)}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Distance</div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-card">
                        <div className="text-sm font-bold text-white">{formatRiskScore(activeSeg.risk_score)}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Risk Score</div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-card">
                        <div className="text-sm font-bold text-white capitalize">{activeSeg.traffic_condition}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Traffic</div>
                      </div>
                    </div>
                  </Card>
                )}
              </CardContent>
            </Card>

            {/* Full segment list */}
            <Card>
              <CardHeader>
                <CardTitle>Route Timeline</CardTitle>
                <CardDescription>Full segment-by-segment breakdown</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {segments.map((seg, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setCurrentSegment(idx);
                        setIsPlaying(false);
                      }}
                      className={cn(
                        'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
                        idx === currentSegment ? 'border-primary/40 bg-primary/5' : 'border-border bg-surface hover:bg-white/5'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div className="text-xs font-mono text-slate-500 w-12">Min {seg.minute}</div>
                        <div>
                          <div className="text-sm text-slate-200 font-medium">{seg.road_name}</div>
                          <div className="text-xs text-slate-500">
                            {seg.road_type} · {formatDistance(seg.distance_km)} · {seg.traffic_condition}
                          </div>
                        </div>
                      </div>
                      <RiskBadge label={seg.risk_label} />
                    </div>
                  ))}
                </div>
                {data.summary && (
                  <div className="mt-4 p-4 rounded-lg bg-surface">
                    <p className="text-sm text-slate-400 leading-relaxed">{data.summary}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}

        {!activeRouteId && (
          <Card className="p-12 text-center">
            <PlaySquare size={40} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              Enter a route ID generated from the Route Planner to run a minute-by-minute simulation
              showing road names, risk levels, and traffic conditions for each segment.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
