'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import './globals.css';

function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <title>SafeRoute AI — Temporal Safety Navigation</title>
        <meta name="description" content="AI-Powered Temporal Safety Navigation System" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="font-sans bg-background text-slate-200 antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
