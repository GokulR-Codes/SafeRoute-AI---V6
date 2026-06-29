import { cn } from '@/lib/utils';

interface LegendItem {
  color: string;
  label: string;
}

interface LegendPanelProps {
  title?: string;
  items: LegendItem[];
  className?: string;
}

export function LegendPanel({ title = 'Risk Legend', items, className }: LegendPanelProps) {
  return (
    <div className={cn('absolute bottom-4 left-4 glass rounded-lg p-3 z-10', className)}>
      <div className="text-xs font-semibold text-slate-300 mb-2">{title}</div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs text-slate-400">
            <span
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: item.color, boxShadow: `0 0 6px ${item.color}80` }}
            />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}

export const RISK_LEGEND_ITEMS: LegendItem[] = [
  { color: '#00E676', label: 'Safe' },
  { color: '#FFC107', label: 'Moderate' },
  { color: '#FF9800', label: 'Caution' },
  { color: '#FF5252', label: 'Danger' },
];
