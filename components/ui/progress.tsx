'use client';

import * as React from 'react';
import * as ProgressPrimitive from '@radix-ui/react-progress';
import { cn } from '@/lib/utils';

export const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { indicatorColor?: string }
>(({ className, value, indicatorColor = '#00E676', ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn('relative h-2 w-full overflow-hidden rounded-full bg-surface border border-border', className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full transition-all duration-500 ease-out rounded-full"
      style={{ width: `${value || 0}%`, backgroundColor: indicatorColor }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = 'Progress';
