'use client';

import { TopNav } from './TopNav';
import { Sidebar } from './Sidebar';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/lib/utils';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useAppStore();

  return (
    <div className="min-h-screen bg-background bg-grid-pattern">
      <TopNav />
      <Sidebar />
      <main
        className={cn(
          'pt-16 transition-all duration-300 min-h-screen',
          sidebarOpen ? 'pl-64' : 'pl-[72px]'
        )}
      >
        <div className="p-6 max-w-[1600px] mx-auto">{children}</div>
      </main>
    </div>
  );
}
