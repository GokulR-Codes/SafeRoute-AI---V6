'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Navigation,
  ShieldCheck,
  Siren,
  Clock,
  TrendingUp,
  PlaySquare,
  Flame,
  ShieldHalf,
  ShieldAlert,
  AlertCircle,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store/appStore';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/route-planner', label: 'Route Planner', icon: Navigation },
  { href: '/women-safety', label: 'Women Safety', icon: ShieldCheck },
  { href: '/emergency-escape', label: 'Emergency Escape', icon: Siren },
  { href: '/time-machine', label: 'Time Machine', icon: Clock },
  { href: '/risk-forecasting', label: 'Risk Forecasting', icon: TrendingUp },
  { href: '/route-simulation', label: 'Route Simulation', icon: PlaySquare },
  { href: '/heatmaps', label: 'Heatmaps', icon: Flame },
  { href: '/safe-zones', label: 'Safe Zones', icon: ShieldHalf },
  { href: '/danger-zones', label: 'Danger Zones', icon: ShieldAlert },
  { href: '/incident-center', label: 'Incident Center', icon: AlertCircle },
  { href: '/explainability', label: 'Explainability AI', icon: BrainCircuit },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        'fixed left-0 top-16 bottom-0 z-40 bg-card border-r border-border transition-all duration-300 flex flex-col',
        sidebarOpen ? 'w-64' : 'w-[72px]'
      )}
    >
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'sidebar-item flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'active bg-primary/10 text-primary'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
              )}
              title={!sidebarOpen ? label : undefined}
            >
              <Icon size={18} className="flex-shrink-0" />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={toggleSidebar}
        className="m-3 flex items-center justify-center rounded-lg border border-border py-2 text-slate-500 hover:text-primary hover:border-primary/30 transition-colors"
      >
        {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
      </button>
    </aside>
  );
}
