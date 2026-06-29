import * as React from 'react';
import { cn } from '@/lib/utils';
import type { RiskLabel } from '@/types';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'safe' | 'moderate' | 'caution' | 'unsafe' | 'outline';
}

const variantClasses: Record<string, string> = {
  default: 'bg-white/10 text-slate-200',
  safe: 'bg-risk-safe risk-safe',
  moderate: 'bg-risk-moderate risk-moderate',
  caution: 'bg-risk-caution risk-caution',
  unsafe: 'bg-risk-unsafe risk-unsafe',
  outline: 'border border-border text-slate-300',
};

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium',
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}

export function RiskBadge({ label }: { label: RiskLabel }) {
  const labels: Record<RiskLabel, string> = {
    safe: 'Safe',
    moderate: 'Moderate',
    caution: 'Caution',
    unsafe: 'Unsafe',
  };
  return <Badge variant={label}>{labels[label]}</Badge>;
}
