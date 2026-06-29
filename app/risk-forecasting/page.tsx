'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { RiskBadge } from '@/components/ui/badge';
import { HourlyForecastChart, RiskComparisonChart } from '@/components/charts/Charts';
import { useRiskForecastMutation } from '@/hooks/useApi';
import { formatHour, formatRiskScore, getTimeOfDayIcon } from '@/lib/utils';
import { MapPin, TrendingUp, TrendingDown, Minus, Loader2, Sparkles } from 'lucide-react';

export default function RiskForecastingPage() {
  const [location, setLocation] = useState('');
  const [targetHour, setTargetHour] = useState(18);

  const mutation = useRiskForecastMutation();
  const data = mutation.data;

  const handlePredict = () => {
    if (!location) return;
    mutation.mutate({ location, target_hour: targetHour });
  };

  const TrendIcon = data?.trend === 'increasing' ? TrendingUp : data?.trend === 'decreasing' ? TrendingDown : Minus;
  const trendColor = data?.trend === 'increasing' ? '#FF5252' : data?.trend === 'decreasing' ? '#00E676' : '#94A3B8';

  const comparisonData = data
    ? [{ label: formatHour(targetHour), current: data.current_risk, predicted: data.predicted_risk }]
    : [];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-warning/10 border border-warning/20 flex items-center justify-center">
            <TrendingUp size={20} className="text-warning" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Risk Forecasting</h1>
            <p className="text-slate-400 text-sm">
              Predict future risk levels using temporal pattern recognition
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Predict Future Risk</CardTitle>
            <CardDescription>Select a location and future hour to generate a risk forecast</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Location</Label>
              <div className="relative">
                <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
                <Input
                  placeholder="Enter location or zone"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <Label className="mb-0">Target Future Hour</Label>
                <span className="text-xs font-mono text-primary">
                  {formatHour(targetHour)} {getTimeOfDayIcon(targetHour)}
                </span>
              </div>
              <Slider value={[targetHour]} onValueChange={([v]) => setTargetHour(v)} min={0} max={23} step={1} />
            </div>

            <Button onClick={handlePredict} disabled={!location || mutation.isPending} size="lg">
              {mutation.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Forecasting...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  Predict Future Risk
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {mutation.isError && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to generate risk forecast. Please check the backend connection and try again.
            </p>
          </Card>
        )}

        {data && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Current Risk</div>
                <div className="font-display font-bold text-2xl text-white">
                  {formatRiskScore(data.current_risk)}
                </div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Predicted Risk</div>
                <div className="font-display font-bold text-2xl text-white">
                  {formatRiskScore(data.predicted_risk)}
                </div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Trend</div>
                <div className="flex items-center gap-2 mt-1">
                  <TrendIcon size={20} style={{ color: trendColor }} />
                  <span className="font-display font-semibold text-white capitalize">{data.trend}</span>
                </div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Risk Label</div>
                <div className="mt-1">
                  <RiskBadge label={data.risk_label} />
                </div>
              </Card>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Risk Forecast Graph</CardTitle>
                  <CardDescription>Predicted risk across the upcoming hours</CardDescription>
                </CardHeader>
                <CardContent>
                  <HourlyForecastChart data={data.hourly_forecast} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Risk Comparison Chart</CardTitle>
                  <CardDescription>Current vs predicted risk at target hour</CardDescription>
                </CardHeader>
                <CardContent>
                  <RiskComparisonChart data={comparisonData} />
                  <div className="mt-4 p-3 rounded-lg bg-surface text-center">
                    <div className="text-xs text-slate-400 mb-1">Prediction Confidence</div>
                    <div className="font-display font-bold text-lg text-white">
                      {formatRiskScore(data.prediction_confidence)}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )}

        {!data && !mutation.isPending && !mutation.isError && (
          <Card className="p-12 text-center">
            <TrendingUp size={40} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              Enter a location and target hour to predict future risk levels using temporal pattern
              recognition from the risk graph engine.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
