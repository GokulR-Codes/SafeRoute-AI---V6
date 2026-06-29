import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { RiskLabel } from '@/types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getRiskColor(risk: number): string {
  if (risk <= 0.25) return '#00E676';
  if (risk <= 0.5) return '#FFC107';
  if (risk <= 0.75) return '#FF9800';
  return '#FF5252';
}

export function getRiskLabel(risk: number): RiskLabel {
  if (risk <= 0.25) return 'safe';
  if (risk <= 0.5) return 'moderate';
  if (risk <= 0.75) return 'caution';
  return 'unsafe';
}

export function getRiskLabelColor(label: RiskLabel): string {
  const colors: Record<RiskLabel, string> = {
    safe: '#00E676',
    moderate: '#FFC107',
    caution: '#FF9800',
    unsafe: '#FF5252',
  };
  return colors[label];
}

export function getRiskBgClass(label: RiskLabel): string {
  const classes: Record<RiskLabel, string> = {
    safe: 'bg-risk-safe text-green-400',
    moderate: 'bg-risk-moderate text-yellow-400',
    caution: 'bg-risk-caution text-orange-400',
    unsafe: 'bg-risk-unsafe text-red-400',
  };
  return classes[label];
}

export function formatRiskScore(score: number): string {
  return (score * 100).toFixed(1) + '%';
}

export function formatDistance(km: number): string {
  if (km < 1) return (km * 1000).toFixed(0) + ' m';
  return km.toFixed(1) + ' km';
}

export function formatTime(minutes: number): string {
  if (minutes < 60) return Math.round(minutes) + ' min';
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${h}h ${m}m`;
}

export function formatHour(hour: number): string {
  if (hour === 0) return '12:00 AM';
  if (hour < 12) return `${hour}:00 AM`;
  if (hour === 12) return '12:00 PM';
  return `${hour - 12}:00 PM`;
}

export function getTimeOfDay(hour: number): string {
  if (hour >= 5 && hour < 12) return 'Morning';
  if (hour >= 12 && hour < 17) return 'Afternoon';
  if (hour >= 17 && hour < 21) return 'Evening';
  return 'Night';
}

export function getTimeOfDayIcon(hour: number): string {
  if (hour >= 5 && hour < 12) return '🌅';
  if (hour >= 12 && hour < 17) return '☀️';
  if (hour >= 17 && hour < 21) return '🌆';
  return '🌙';
}

export function interpolateColor(color1: string, color2: string, t: number): string {
  const hex1 = color1.replace('#', '');
  const hex2 = color2.replace('#', '');
  const r1 = parseInt(hex1.substring(0, 2), 16);
  const g1 = parseInt(hex1.substring(2, 4), 16);
  const b1 = parseInt(hex1.substring(4, 6), 16);
  const r2 = parseInt(hex2.substring(0, 2), 16);
  const g2 = parseInt(hex2.substring(2, 4), 16);
  const b2 = parseInt(hex2.substring(4, 6), 16);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

export function truncate(str: string, n: number): string {
  return str.length > n ? str.substring(0, n - 1) + '...' : str;
}

export const INCIDENT_ICONS: Record<string, string> = {
  accident: '🚗',
  flood: '🌊',
  crime: '⚠️',
  road_closure: '🚧',
  construction: '🏗️',
  event: '🎉',
};

export const EMERGENCY_ICONS: Record<string, string> = {
  police_station: '🚔',
  hospital: '🏥',
  metro_station: '🚇',
  public_area: '🏛️',
  cctv_zone: '📹',
};

export const EMERGENCY_LABELS: Record<string, string> = {
  police_station: 'Police Station',
  hospital: 'Hospital',
  metro_station: 'Metro Station',
  public_area: 'Public Area',
  cctv_zone: 'CCTV Dense Zone',
};
