import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
  trend?: { value: string; positive: boolean };
  suffix?: string;
}

export function MetricCard({ label, value, icon: Icon, color = '#00E676', trend, suffix }: MetricCardProps) {
  return (
    <Card className="metric-card p-5">
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ background: `${color}15` }}
        >
          <Icon size={20} style={{ color }} />
        </div>
        {trend && (
          <span
            className={cn(
              'text-xs font-medium px-2 py-0.5 rounded-full',
              trend.positive ? 'text-primary bg-primary/10' : 'text-danger bg-danger/10'
            )}
          >
            {trend.value}
          </span>
        )}
      </div>
      <div className="font-display font-bold text-2xl text-white mb-1">
        {value}
        {suffix && <span className="text-sm text-slate-500 font-normal ml-1">{suffix}</span>}
      </div>
      <div className="text-xs text-slate-400">{label}</div>
    </Card>
  );
}
