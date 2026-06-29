'use client';

import { AppShell } from '@/components/layout/AppShell';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import {
  RiskDistributionChart,
  TravelTimeDistributionChart,
  ZoneRiskChart,
} from '@/components/charts/Charts';
import { RiskBadge } from '@/components/ui/badge';
import { useAnalytics } from '@/hooks/useApi';
import { getRiskLabel, formatRiskScore, formatTime } from '@/lib/utils';
import {
  Navigation,
  Activity,
  Clock,
  Gauge,
  ShieldHalf,
  ShieldAlert,
  AlertCircle,
  TrendingUp,
} from 'lucide-react';

export default function DashboardPage() {
  const { data, isLoading, error } = useAnalytics();

  const riskDistData = data
    ? [
        { name: 'Safe', value: data.risk_distribution.safe },
        { name: 'Moderate', value: data.risk_distribution.moderate },
        { name: 'Caution', value: data.risk_distribution.caution },
        { name: 'Unsafe', value: data.risk_distribution.unsafe },
      ]
    : [];

  const zoneRiskData = data?.zone_risk_overview ?? [];
  const travelTimeData = data?.travel_time_distribution ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="font-display font-bold text-2xl text-white mb-1">
            System Dashboard
          </h1>
          <p className="text-slate-400 text-sm">
            Real-time overview of SafeRoute AI temporal risk intelligence engine
          </p>
        </div>

        {error && (
          <Card className="p-4 border-danger/30 bg-danger/5">
            <p className="text-danger text-sm">
              Unable to connect to analytics engine. Displaying placeholder data.
            </p>
          </Card>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Routes Generated"
            value={isLoading ? '—' : data?.total_routes_generated.toLocaleString() ?? '0'}
            icon={Navigation}
            color="#00E676"
          />
          <MetricCard
            label="Average Route Risk"
            value={isLoading ? '—' : formatRiskScore(data?.average_route_risk ?? 0)}
            icon={Activity}
            color="#FFC107"
          />
          <MetricCard
            label="Average Travel Time"
            value={isLoading ? '—' : formatTime(data?.average_travel_time_min ?? 0)}
            icon={Clock}
            color="#00BFA5"
          />
          <MetricCard
            label="Average Confidence Score"
            value={isLoading ? '—' : formatRiskScore(data?.average_confidence_score ?? 0)}
            icon={Gauge}
            color="#9C27B0"
          />
          <MetricCard
            label="Safe Zones Count"
            value={isLoading ? '—' : data?.safe_zones_count ?? '0'}
            icon={ShieldHalf}
            color="#00E676"
          />
          <MetricCard
            label="Danger Zones Count"
            value={isLoading ? '—' : data?.danger_zones_count ?? '0'}
            icon={ShieldAlert}
            color="#FF5252"
          />
          <MetricCard
            label="Active Incidents"
            value={isLoading ? '—' : data?.active_incidents ?? '0'}
            icon={AlertCircle}
            color="#FF9800"
          />
          <MetricCard
            label="System Status"
            value="Operational"
            icon={TrendingUp}
            color="#00E676"
          />
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Risk Distribution</CardTitle>
              <CardDescription>Breakdown of all analyzed routes by risk category</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-60 skeleton rounded-lg" />
              ) : (
                <RiskDistributionChart data={riskDistData} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Travel Time Distribution</CardTitle>
              <CardDescription>Distribution of route travel times across the network</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-60 skeleton rounded-lg" />
              ) : (
                <TravelTimeDistributionChart data={travelTimeData} />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Zone Risk Overview</CardTitle>
              <CardDescription>Average risk score across major zones</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-60 skeleton rounded-lg" />
              ) : (
                <ZoneRiskChart data={zoneRiskData} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Route Analytics</CardTitle>
              <CardDescription>Latest routes processed by the recommendation engine</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-12 skeleton rounded-lg" />
                  ))}
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {(data?.recent_routes ?? []).map((route) => (
                    <div
                      key={route.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-surface border border-border"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-slate-200 font-medium truncate">
                          {route.source} → {route.destination}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">{route.time}</div>
                      </div>
                      <RiskBadge label={getRiskLabel(route.risk)} />
                    </div>
                  ))}
                  {(!data?.recent_routes || data.recent_routes.length === 0) && (
                    <div className="text-center text-slate-500 text-sm py-8">
                      No recent routes available
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
