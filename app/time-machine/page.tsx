'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { RiskBadge } from '@/components/ui/badge';
import { RiskTrendChart, TravelTimeChart, CostTrendChart } from '@/components/charts/Charts';
import { useTimeMachineMutation } from '@/hooks/useApi';
import { formatHour, formatTime, formatRiskScore, getTimeOfDay, getTimeOfDayIcon, cn } from '@/lib/utils';
import { MapPin, Clock, Loader2, Sparkles, TrendingDown, TrendingUp } from 'lucide-react';
import type { TimeSlotAnalysis } from '@/types';

const TIME_PERIODS = [
  { label: 'Morning', hours: [5, 11], icon: '🌅' },
  { label: 'Afternoon', hours: [12, 16], icon: '☀️' },
  { label: 'Evening', hours: [17, 20], icon: '🌆' },
  { label: 'Night', hours: [21, 4], icon: '🌙' },
];

export default function TimeMachinePage() {
  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [selectedHour, setSelectedHour] = useState<number | null>(null);

  const mutation = useTimeMachineMutation();
  const data = mutation.data;

  const handleAnalyze = () => {
    if (!source || !destination) return;
    mutation.mutate({ source, destination });
    setSelectedHour(null);
  };

  const hourly = data?.hourly_analysis ?? [];

  const groupByPeriod = (period: { hours: number[] }) => {
    const [start, end] = period.hours;
    return hourly.filter((h) => {
      if (start <= end) return h.hour >= start && h.hour <= end;
      return h.hour >= start || h.hour <= end; // wraps midnight
    });
  };

  const activeSlot = selectedHour !== null ? hourly.find((h) => h.hour === selectedHour) : null;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-secondary/10 border border-secondary/20 flex items-center justify-center">
            <Clock size={20} className="text-secondary" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Time Machine Routing</h1>
            <p className="text-slate-400 text-sm">
              Compare route conditions across all 24 hours of the day
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Analyze Route Across Time</CardTitle>
            <CardDescription>Enter a route to see how risk and travel time vary by hour</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
                <Input placeholder="Source" value={source} onChange={(e) => setSource(e.target.value)} className="pl-9" />
              </div>
              <div className="relative flex-1">
                <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-danger" />
                <Input placeholder="Destination" value={destination} onChange={(e) => setDestination(e.target.value)} className="pl-9" />
              </div>
              <Button onClick={handleAnalyze} disabled={!source || !destination || mutation.isPending} size="lg">
                {mutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Run Time Machine
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {mutation.isError && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to analyze route over time. Please check the backend connection and try again.
            </p>
          </Card>
        )}

        {data && (
          <>
            {/* Best/worst hour summary */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Card className="p-5 border-primary/20 bg-primary/5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <TrendingDown size={20} className="text-primary" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Best Time to Travel</div>
                    <div className="font-display font-bold text-white text-lg">
                      {formatHour(data.best_hour)} {getTimeOfDayIcon(data.best_hour)}
                    </div>
                  </div>
                </div>
              </Card>
              <Card className="p-5 border-danger/20 bg-danger/5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-danger/10 flex items-center justify-center">
                    <TrendingUp size={20} className="text-danger" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Highest Risk Time</div>
                    <div className="font-display font-bold text-white text-lg">
                      {formatHour(data.worst_hour)} {getTimeOfDayIcon(data.worst_hour)}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Summary text */}
            <Card className="p-5">
              <p className="text-sm text-slate-400 leading-relaxed">{data.summary}</p>
            </Card>

            {/* Time period comparison */}
            <Card>
              <CardHeader>
                <CardTitle>Compare by Time Period</CardTitle>
                <CardDescription>Click an hour below to view detailed conditions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                  {TIME_PERIODS.map((period) => {
                    const slots = groupByPeriod(period);
                    const avgRisk =
                      slots.reduce((sum, s) => sum + s.risk_score, 0) / (slots.length || 1);
                    const avgTime =
                      slots.reduce((sum, s) => sum + s.travel_time_min, 0) / (slots.length || 1);

                    return (
                      <Card key={period.label} className="p-4 bg-surface border-border">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-semibold text-white">
                            {period.icon} {period.label}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 mb-1">Avg Risk</div>
                        <div className="text-lg font-display font-bold text-white mb-2">
                          {formatRiskScore(avgRisk)}
                        </div>
                        <div className="text-xs text-slate-400 mb-1">Avg Time</div>
                        <div className="text-sm font-medium text-slate-300">{formatTime(avgTime)}</div>
                      </Card>
                    );
                  })}
                </div>

                {/* 24h hour selector grid */}
                <div className="grid grid-cols-6 sm:grid-cols-12 gap-2">
                  {hourly.map((slot) => (
                    <button
                      key={slot.hour}
                      onClick={() => setSelectedHour(slot.hour)}
                      className={cn(
                        'p-2 rounded-lg border text-center transition-all',
                        selectedHour === slot.hour
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-surface hover:border-white/20'
                      )}
                    >
                      <div className="text-xs font-mono text-slate-400">{slot.hour}:00</div>
                      <div
                        className="w-2 h-2 rounded-full mx-auto mt-1"
                        style={{
                          backgroundColor:
                            slot.safety_label === 'safe'
                              ? '#00E676'
                              : slot.safety_label === 'moderate'
                              ? '#FFC107'
                              : slot.safety_label === 'caution'
                              ? '#FF9800'
                              : '#FF5252',
                        }}
                      />
                    </button>
                  ))}
                </div>

                {activeSlot && (
                  <Card className="mt-4 p-4 bg-primary/5 border-primary/20">
                    <div className="flex items-center justify-between mb-3">
                      <div className="font-display font-semibold text-white">
                        {formatHour(activeSlot.hour)} — {getTimeOfDay(activeSlot.hour)} {getTimeOfDayIcon(activeSlot.hour)}
                      </div>
                      <RiskBadge label={activeSlot.safety_label} />
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div>
                        <div className="text-lg font-display font-bold text-white">
                          {formatRiskScore(activeSlot.risk_score)}
                        </div>
                        <div className="text-xs text-slate-500">Risk Score</div>
                      </div>
                      <div>
                        <div className="text-lg font-display font-bold text-white">
                          {formatTime(activeSlot.travel_time_min)}
                        </div>
                        <div className="text-xs text-slate-500">Travel Time</div>
                      </div>
                      <div>
                        <div className="text-lg font-display font-bold text-white">
                          {activeSlot.route_cost.toFixed(2)}
                        </div>
                        <div className="text-xs text-slate-500">Route Cost</div>
                      </div>
                    </div>
                  </Card>
                )}
              </CardContent>
            </Card>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Risk Trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <RiskTrendChart data={hourly} dataKey="risk_score" xKey="hour" />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Travel Time Trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <TravelTimeChart data={hourly} dataKey="travel_time_min" xKey="hour" />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Cost Trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <CostTrendChart data={hourly} dataKey="route_cost" xKey="hour" />
                </CardContent>
              </Card>
            </div>
          </>
        )}

        {!data && !mutation.isPending && !mutation.isError && (
          <Card className="p-12 text-center">
            <Clock size={40} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              Enter a source and destination to compare risk scores, travel times, and route costs
              across all 24 hours of the day.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
