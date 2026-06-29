import { Card } from '@/components/ui/card';
import { RiskBadge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn, formatDistance, formatTime, formatRiskScore, getRiskColor, getRiskLabel } from '@/lib/utils';
import type { RouteRecommendation } from '@/types';
import { Navigation, Gauge, ChevronRight } from 'lucide-react';

interface RouteComparisonPanelProps {
  routes: RouteRecommendation[];
  selectedRouteId: string | null;
  onSelectRoute: (route: RouteRecommendation) => void;
}

export function RouteComparisonPanel({ routes, selectedRouteId, onSelectRoute }: RouteComparisonPanelProps) {
  return (
    <div className="space-y-3">
      {routes.map((route) => {
        const isSelected = route.route_id === selectedRouteId;
        const riskColor = getRiskColor(route.avg_risk);

        return (
          <Card
            key={route.route_id}
            onClick={() => onSelectRoute(route)}
            className={cn(
              'p-4 cursor-pointer transition-all duration-200',
              isSelected
                ? 'border-primary/40 glow-border bg-primary/5'
                : 'hover:border-white/10 hover:bg-white/[0.02]'
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center"
                  style={{ background: `${riskColor}15` }}
                >
                  <Navigation size={16} style={{ color: riskColor }} />
                </div>
                <div>
                  <div className="font-display font-semibold text-white text-sm">
                    {route.label}
                  </div>
                  <div className="text-xs text-slate-500 capitalize">{route.safety_profile}</div>
                </div>
              </div>
              <RiskBadge label={route.risk_label ?? getRiskLabel(route.avg_risk)} />
            </div>

            <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
              <div>
                <div className="text-slate-500 mb-0.5">Distance</div>
                <div className="text-slate-200 font-medium">{formatDistance(route.distance_km)}</div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Travel Time</div>
                <div className="text-slate-200 font-medium">{formatTime(route.travel_time_min)}</div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Avg Risk</div>
                <div className="text-slate-200 font-medium">{formatRiskScore(route.avg_risk)}</div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Max Risk</div>
                <div className="text-slate-200 font-medium">{formatRiskScore(route.max_risk)}</div>
              </div>
            </div>

            {/* Confidence score */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Gauge size={12} />
                  Confidence Score
                </div>
                <span className="text-xs font-mono text-slate-300">
                  {formatRiskScore(route.confidence_score)}
                </span>
              </div>
              <Progress value={route.confidence_score * 100} indicatorColor="#00BFA5" />
            </div>

            {/* Explanation */}
            <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
              {route.explanation}
            </p>

            {isSelected && (
              <div className="flex items-center gap-1 text-xs text-primary mt-2 font-medium">
                Selected on map
                <ChevronRight size={12} />
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
