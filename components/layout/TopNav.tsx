'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Navigation, Bell, Clock, Wifi } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { formatHour, getTimeOfDayIcon } from '@/lib/utils';
import { useEffect, useState } from 'react';

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/route-planner': 'Route Planner',
  '/women-safety': 'Women Safety Routing',
  '/emergency-escape': 'Emergency Escape',
  '/time-machine': 'Time Machine',
  '/risk-forecasting': 'Risk Forecasting',
  '/route-simulation': 'Route Simulation',
  '/heatmaps': 'Risk Heatmaps',
  '/safe-zones': 'Safe Zones',
  '/danger-zones': 'Danger Zones',
  '/incident-center': 'Incident Center',
  '/explainability': 'Explainability AI',
};

export function TopNav() {
  const pathname = usePathname();
  const { currentHour, activeIncidents } = useAppStore();
  const [liveTime, setLiveTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setLiveTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-card/80 backdrop-blur-xl border-b border-border flex items-center justify-between px-6">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
            <Navigation size={16} className="text-primary" />
          </div>
          <span className="font-display font-bold text-white hidden sm:inline">SafeRoute AI</span>
        </Link>

        <div className="hidden md:block h-6 w-px bg-border" />

        <h1 className="font-display font-semibold text-slate-200 hidden md:block">
          {pageTitles[pathname] || 'SafeRoute AI'}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        {/* System status */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-xs text-primary font-mono">
          <Wifi size={12} />
          ENGINE ONLINE
        </div>

        {/* Current hour context */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-border text-xs text-slate-400 font-mono">
          <span>{getTimeOfDayIcon(currentHour)}</span>
          {formatHour(currentHour)}
        </div>

        {/* Live clock */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-border text-xs text-slate-400 font-mono">
          <Clock size={12} />
          {liveTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-white/5 transition-colors text-slate-400 hover:text-white">
          <Bell size={18} />
          {activeIncidents.length > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-danger animate-pulse" />
          )}
        </button>
      </div>
    </header>
  );
}
