'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Badge, RiskBadge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useRouteExplanation } from '@/hooks/useApi';
import { formatDistance, formatTime, formatRiskScore, getRiskLabel } from '@/lib/utils';
import {
  BrainCircuit,
  CheckCircle2,
  XCircle,
  Route,
  TrendingDown,
  Search,
  Sparkles,
} from 'lucide-react';

export default function ExplainabilityPage() {
  const [routeId, setRouteId] = useState('');
  const [activeRouteId, setActiveRouteId] = useState<string | null>(null);

  const { data, isLoading, error } = useRouteExplanation(activeRouteId);

  const handleLoad = () => {
    if (!routeId) return;
    setActiveRouteId(routeId);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
            <BrainCircuit size={20} className="text-purple-400" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Explainability AI</h1>
            <p className="text-slate-400 text-sm">
              Full reasoning breakdown for why a route was recommended
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Load Route Explanation</CardTitle>
            <CardDescription>Enter a route ID from the Route Planner to view AI reasoning</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input
                  placeholder="Enter route ID (e.g. route-a-12345)"
                  value={routeId}
                  onChange={(e) => setRouteId(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Button onClick={handleLoad} disabled={!routeId} size="lg">
                <Sparkles size={16} />
                Explain Route
              </Button>
            </div>
          </CardContent>
        </Card>

        {error && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Failed to load route explanation. Please verify the route ID and backend connection.
            </p>
          </Card>
        )}

        {isLoading && (
          <Card className="p-12 text-center">
            <div className="skeleton h-4 w-1/2 mx-auto rounded-full mb-4" />
            <div className="skeleton h-4 w-1/3 mx-auto rounded-full" />
          </Card>
        )}

        {data && (
          <>
            {/* Header summary */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Selected Route</div>
                <div className="font-display font-bold text-lg text-white truncate">{data.selected_route}</div>
                <div className="text-xs text-slate-500 mt-1 capitalize">{data.route_profile}</div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Average Risk</div>
                <div className="font-display font-bold text-lg text-white">{formatRiskScore(data.avg_risk)}</div>
                <RiskBadge label={getRiskLabel(data.avg_risk)} />
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Travel Time</div>
                <div className="font-display font-bold text-lg text-white">{formatTime(data.travel_time_min)}</div>
                <div className="text-xs text-slate-500 mt-1">{formatDistance(data.distance_km)}</div>
              </Card>
              <Card className="p-5">
                <div className="text-xs text-slate-400 mb-1">Confidence Score</div>
                <div className="font-display font-bold text-lg text-white mb-2">{formatRiskScore(data.confidence_score)}</div>
                <Progress value={data.confidence_score * 100} indicatorColor="#9C27B0" />
              </Card>
            </div>

            {/* Risk reduction highlight */}
            <Card className="p-6 bg-primary/5 border-primary/20">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <TrendingDown size={24} className="text-primary" />
                </div>
                <div>
                  <div className="text-sm text-slate-400">Risk Reduction vs Alternatives</div>
                  <div className="font-display font-bold text-3xl text-primary">
                    {data.risk_reduction_pct.toFixed(1)}%
                  </div>
                </div>
              </div>
            </Card>

            {/* AI Reasoning panel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BrainCircuit size={16} className="text-purple-400" />
                  AI Reasoning Panel
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-slate-300 leading-relaxed">{data.ai_reasoning}</p>

                {data.reasoning_steps?.length > 0 && (
                  <div className="space-y-2">
                    {data.reasoning_steps.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-surface">
                        <div className="w-6 h-6 rounded-full bg-purple-500/10 flex items-center justify-center text-xs font-mono text-purple-400 flex-shrink-0 mt-0.5">
                          {idx + 1}
                        </div>
                        <p className="text-sm text-slate-400 leading-relaxed">{step}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Visual explanation cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="text-primary" />
                    Major Roads Used
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {data.major_roads_used.map((road) => (
                      <Badge key={road} variant="safe">
                        <Route size={10} />
                        {road}
                      </Badge>
                    ))}
                    {data.major_roads_used.length === 0 && (
                      <p className="text-sm text-slate-500">No major roads recorded.</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <XCircle size={16} className="text-danger" />
                    High Risk Segments Avoided
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {data.high_risk_segments_avoided.map((seg) => (
                      <Badge key={seg} variant="unsafe">
                        <Route size={10} />
                        {seg}
                      </Badge>
                    ))}
                    {data.high_risk_segments_avoided.length === 0 && (
                      <p className="text-sm text-slate-500">No high-risk segments avoided.</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Alternative comparison */}
            <Card>
              <CardHeader>
                <CardTitle>Alternative Comparison</CardTitle>
                <CardDescription>How the selected route compares to alternatives</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-slate-500 border-b border-border">
                        <th className="py-2 pr-4">Route</th>
                        <th className="py-2 pr-4">Risk</th>
                        <th className="py-2 pr-4">Travel Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.alternative_comparison.map((alt) => (
                        <tr key={alt.route} className="border-b border-border/50">
                          <td className="py-3 pr-4 text-slate-200 font-medium">{alt.route}</td>
                          <td className="py-3 pr-4">
                            <RiskBadge label={getRiskLabel(alt.risk)} />
                          </td>
                          <td className="py-3 pr-4 text-slate-400">{formatTime(alt.time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {!activeRouteId && (
          <Card className="p-12 text-center">
            <BrainCircuit size={40} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              Enter a route ID from the Route Planner to see a full explainable AI breakdown:
              reasoning steps, roads used, high-risk segments avoided, and alternative comparisons.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
