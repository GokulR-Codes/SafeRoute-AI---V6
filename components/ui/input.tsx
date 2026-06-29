import * as React from 'react';
import { cn } from '@/lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-500 outline-none transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/30',
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn('text-xs font-medium text-slate-400 mb-1.5 block', className)}
        {...props}
      />
    );
  }
);
Label.displayName = 'Label';
