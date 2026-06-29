'use client';

import { getRiskColor } from '@/lib/utils';

interface SafetyGaugeProps {
  score: number; // 0 to 1
  label?: string;
  size?: number;
}

export function SafetyGauge({ score, label = 'Safety Score', size = 200 }: SafetyGaugeProps) {
  const percentage = score * 100;
  const radius = size / 2 - 16;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference - (percentage / 100) * circumference;

  // Higher score = safer = greener
  const color = getRiskColor(1 - score);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size / 2 + 20 }}>
        <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
          {/* Background arc */}
          <path
            d={`M 16 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 16} ${size / 2}`}
            fill="none"
            stroke="#1E293B"
            strokeWidth="14"
            strokeLinecap="round"
          />
          {/* Value arc */}
          <path
            d={`M 16 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 16} ${size / 2}`}
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              filter: `drop-shadow(0 0 8px ${color}60)`,
              transition: 'stroke-dashoffset 1s ease-out, stroke 1s ease-out',
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
          <span className="font-display font-bold text-3xl text-white" style={{ color }}>
            {percentage.toFixed(0)}%
          </span>
        </div>
      </div>
      <div className="text-sm text-slate-400 mt-2 text-center">{label}</div>
    </div>
  );
}
