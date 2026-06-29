'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Shield,
  Navigation,
  Clock,
  Zap,
  Eye,
  AlertTriangle,
  Map,
  Activity,
  ChevronRight,
  ArrowRight,
  Globe,
  Cpu,
  BarChart3,
  Radio,
} from 'lucide-react';

// Animated route SVG background
function RouteBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <svg
        className="absolute inset-0 w-full h-full opacity-20"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="routeGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00E676" stopOpacity="0" />
            <stop offset="50%" stopColor="#00E676" stopOpacity="1" />
            <stop offset="100%" stopColor="#00BFA5" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="routeGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#FFC107" stopOpacity="0" />
            <stop offset="50%" stopColor="#FFC107" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#FF5252" stopOpacity="0" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Grid lines */}
        {Array.from({ length: 20 }).map((_, i) => (
          <line
            key={`v${i}`}
            x1={i * 80}
            y1="0"
            x2={i * 80}
            y2="900"
            stroke="#1E293B"
            strokeWidth="1"
          />
        ))}
        {Array.from({ length: 15 }).map((_, i) => (
          <line
            key={`h${i}`}
            x1="0"
            y1={i * 70}
            x2="1440"
            y2={i * 70}
            stroke="#1E293B"
            strokeWidth="1"
          />
        ))}

        {/* Safe route (green) */}
        <path
          d="M 100 700 Q 300 500 500 400 T 900 300 T 1300 200"
          fill="none"
          stroke="url(#routeGrad1)"
          strokeWidth="3"
          filter="url(#glow)"
          strokeDasharray="15 8"
          style={{ animation: 'routeDash 3s linear infinite' }}
        />

        {/* Warning route (yellow) */}
        <path
          d="M 150 750 Q 400 600 600 500 T 1000 400 T 1350 300"
          fill="none"
          stroke="url(#routeGrad2)"
          strokeWidth="2"
          strokeDasharray="10 6"
          style={{ animation: 'routeDash 2s linear infinite reverse' }}
        />

        {/* Node dots */}
        {[
          [100, 700], [300, 550], [500, 400], [700, 340], [900, 300], [1100, 250], [1300, 200],
        ].map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="6" fill="#00E676" opacity="0.6" filter="url(#glow)" />
            <circle cx={x} cy={y} r="12" fill="#00E676" opacity="0.1" />
          </g>
        ))}

        {/* Danger nodes */}
        {[[600, 500], [800, 450]].map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="8" fill="#FF5252" opacity="0.5" filter="url(#glow)" />
            <circle cx={x} cy={y} r="20" fill="#FF5252" opacity="0.05" />
          </g>
        ))}
      </svg>

      {/* Radial gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 50% 50%, transparent 40%, #0A0F1F 80%)',
        }}
      />
    </div>
  );
}

function StatCard({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="text-center">
      <div className="text-3xl font-bold font-display" style={{ color }}>
        {value}
      </div>
      <div className="text-sm text-slate-400 mt-1">{label}</div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
  color,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  color: string;
}) {
  return (
    <div className="group glass rounded-xl p-6 hover:scale-[1.02] transition-all duration-300 cursor-default border border-white/5 hover:border-primary/20">
      <div
        className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
        style={{ background: `${color}15` }}
      >
        <Icon size={24} style={{ color }} />
      </div>
      <h3 className="font-display font-semibold text-white mb-2 text-lg">{title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}

function HowItWorksStep({
  step,
  title,
  description,
}: {
  step: number;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-4 group">
      <div className="flex-shrink-0">
        <div className="w-10 h-10 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary font-bold font-mono text-sm">
          {step.toString().padStart(2, '0')}
        </div>
      </div>
      <div>
        <h4 className="font-display font-semibold text-white mb-1">{title}</h4>
        <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      {/* Navbar */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          background:
            scrollY > 50
              ? 'rgba(10, 15, 31, 0.95)'
              : 'transparent',
          backdropFilter: scrollY > 50 ? 'blur(20px)' : 'none',
          borderBottom: scrollY > 50 ? '1px solid rgba(30, 41, 59, 0.8)' : 'none',
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
              <Navigation size={16} className="text-primary" />
            </div>
            <span className="font-display font-bold text-white">SafeRoute AI</span>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-white transition-colors">
              How It Works
            </a>
            <a href="#architecture" className="hover:text-white transition-colors">
              Architecture
            </a>
          </div>

          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-4 py-2 bg-primary text-black font-semibold text-sm rounded-lg hover:bg-primary/90 transition-all hover:shadow-glow-green"
          >
            Launch Platform
            <ArrowRight size={14} />
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <RouteBackground />

        <div className="relative z-10 text-center px-6 max-w-5xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-8">
            <Radio size={14} className="animate-pulse" />
            AI-Powered Temporal Safety Navigation System
          </div>

          {/* Headline */}
          <h1 className="font-display font-bold text-6xl md:text-8xl text-white leading-tight mb-6">
            Navigate{' '}
            <span
              className="glow-text"
              style={{
                background: 'linear-gradient(135deg, #00E676, #00BFA5)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Safer.
            </span>
            <br />
            Predict{' '}
            <span
              style={{
                background: 'linear-gradient(135deg, #FFC107, #FF9800)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Smarter.
            </span>
          </h1>

          <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed">
            SafeRoute AI uses temporal risk intelligence and explainable AI routing to guide users
            through safer routes — powered by real-time incident data and predictive risk graphs.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-20">
            <Link
              href="/dashboard"
              className="group flex items-center justify-center gap-2 px-8 py-4 bg-primary text-black font-bold rounded-xl text-lg hover:bg-primary/90 transition-all hover:shadow-glow-green"
            >
              Launch Platform
              <ArrowRight
                size={18}
                className="group-hover:translate-x-1 transition-transform"
              />
            </Link>
            <a
              href="#features"
              className="flex items-center justify-center gap-2 px-8 py-4 bg-white/5 border border-white/10 text-white font-semibold rounded-xl text-lg hover:bg-white/10 transition-all"
            >
              View Features
              <ChevronRight size={18} />
            </a>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-12">
            <StatCard value="< 200ms" label="Route Generation" color="#00E676" />
            <StatCard value="24/7" label="Temporal Analysis" color="#00BFA5" />
            <StatCard value="XAI" label="Explainable AI" color="#FFC107" />
            <StatCard value="5+M" label="Risk Nodes" color="#FF9800" />
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <div className="w-6 h-10 border-2 border-white/20 rounded-full flex items-start justify-center pt-2">
            <div className="w-1 h-3 bg-primary rounded-full animate-float" />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-32 px-6 relative">
        <div
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 50%, #00E676 0%, transparent 50%), radial-gradient(circle at 80% 50%, #00BFA5 0%, transparent 50%)",
          }}
        />

        <div className="max-w-7xl mx-auto relative">
          <div className="text-center mb-20">
            <div className="inline-flex items-center gap-2 text-primary text-sm font-medium mb-4">
              <Zap size={14} />
              CORE CAPABILITIES
            </div>
            <h2 className="font-display font-bold text-4xl md:text-5xl text-white mb-4">
              Routing Engine Features
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Every feature powered by a live temporal risk graph engine with real-time incident integration.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={Navigation}
              title="Multi-Profile Route Planning"
              description="Generate Safest, Fastest, and Balanced routes with confidence scoring and full risk breakdown per segment."
              color="#00E676"
            />
            <FeatureCard
              icon={Clock}
              title="Time Machine Routing"
              description="Compare how the same route changes across all 24 hours. Know the safest time window before you travel."
              color="#00BFA5"
            />
            <FeatureCard
              icon={Shield}
              title="Women Safety Routing"
              description="Lighting analysis, isolation detection, and safety scoring engineered specifically for women's safety."
              color="#FF6B9D"
            />
            <FeatureCard
              icon={AlertTriangle}
              title="Emergency Escape Routing"
              description="Instant routing to nearest police, hospital, metro, and CCTV-dense zones in real-time emergencies."
              color="#FF5252"
            />
            <FeatureCard
              icon={Activity}
              title="Predictive Risk Analysis"
              description="Forecast risk levels for any future hour using temporal pattern recognition and trend analysis."
              color="#FFC107"
            />
            <FeatureCard
              icon={Map}
              title="Risk Heatmaps"
              description="Visualize city-wide risk distribution with safe and danger zone overlays filtered by hour."
              color="#FF9800"
            />
            <FeatureCard
              icon={Eye}
              title="Explainable AI"
              description="Full reasoning panels showing why a route was recommended, roads avoided, and AI decision logic."
              color="#9C27B0"
            />
            <FeatureCard
              icon={BarChart3}
              title="Route Simulation"
              description="Minute-by-minute simulation of your journey with per-segment risk, traffic, and road type data."
              color="#2196F3"
            />
            <FeatureCard
              icon={Cpu}
              title="Live Incident Center"
              description="Create and remove incidents (accidents, floods, crimes) that instantly update risk scores across the graph."
              color="#00BFA5"
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-32 px-6 bg-surface/50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-20">
            <div className="inline-flex items-center gap-2 text-secondary text-sm font-medium mb-4">
              <Globe size={14} />
              UNDER THE HOOD
            </div>
            <h2 className="font-display font-bold text-4xl md:text-5xl text-white mb-4">
              How It Works
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-8">
              <HowItWorksStep
                step={1}
                title="Temporal Risk Graph Construction"
                description="Road network represented as a weighted graph where edge weights reflect time-varying risk scores computed from historical incident data."
              />
              <HowItWorksStep
                step={2}
                title="Multi-Factor Risk Scoring"
                description="Each road segment scored across crime rates, lighting conditions, traffic density, historical accidents, and time-of-day patterns."
              />
              <HowItWorksStep
                step={3}
                title="AI Route Selection"
                description="Modified Dijkstra/A* algorithm traverses the temporal risk graph to return top-3 routes across safety profiles."
              />
              <HowItWorksStep
                step={4}
                title="Explainable Output"
                description="Each recommended route comes with step-by-step reasoning, avoided segments, and confidence scores for full transparency."
              />
            </div>

            <div className="relative">
              <div className="glass rounded-2xl p-6 border border-white/5 h-full min-h-[400px] flex flex-col gap-4">
                <div className="flex items-center gap-2 text-sm text-slate-400 font-mono mb-2">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  RISK ENGINE OUTPUT
                </div>

                {/* Mock output cards */}
                {[
                  {
                    route: 'Route A — Safest',
                    risk: '8.2%',
                    time: '14 min',
                    conf: '94%',
                    color: '#00E676',
                  },
                  {
                    route: 'Route B — Balanced',
                    risk: '23.1%',
                    time: '11 min',
                    conf: '87%',
                    color: '#FFC107',
                  },
                  {
                    route: 'Route C — Fastest',
                    risk: '41.7%',
                    time: '8 min',
                    conf: '79%',
                    color: '#FF9800',
                  },
                ].map((r) => (
                  <div
                    key={r.route}
                    className="flex items-center justify-between p-4 rounded-xl border"
                    style={{ borderColor: `${r.color}20`, background: `${r.color}08` }}
                  >
                    <div>
                      <div className="text-white font-medium text-sm">{r.route}</div>
                      <div className="text-slate-400 text-xs mt-0.5">
                        Risk: {r.risk} · {r.time}
                      </div>
                    </div>
                    <div
                      className="text-sm font-bold font-mono"
                      style={{ color: r.color }}
                    >
                      {r.conf}
                    </div>
                  </div>
                ))}

                <div className="mt-auto p-4 rounded-xl bg-primary/5 border border-primary/10">
                  <div className="text-xs text-primary font-mono mb-1">AI REASONING</div>
                  <div className="text-xs text-slate-400 leading-relaxed">
                    Route A selected: 78% lower risk than Route C. Avoids MG Road
                    (crime hotspot, 18:00–23:00). 3 high-risk intersections bypassed.
                    Confidence: 94%.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture Section */}
      <section id="architecture" className="py-32 px-6">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 text-primary text-sm font-medium mb-4">
            <Cpu size={14} />
            SYSTEM DESIGN
          </div>
          <h2 className="font-display font-bold text-4xl md:text-5xl text-white mb-4">
            System Architecture
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto mb-16">
            A multi-engine backend connected to a real-time risk graph, powering every
            feature with temporal intelligence.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {[
              { label: 'Route Engine', icon: Navigation, color: '#00E676' },
              { label: 'Risk Graph', icon: Activity, color: '#FFC107' },
              { label: 'Temporal AI', icon: Clock, color: '#00BFA5' },
              { label: 'Incident Layer', icon: AlertTriangle, color: '#FF5252' },
            ].map(({ label, icon: Icon, color }) => (
              <div key={label} className="glass rounded-xl p-5 border border-white/5">
                <Icon size={28} style={{ color }} className="mx-auto mb-3" />
                <div className="text-white font-medium text-sm">{label}</div>
              </div>
            ))}
          </div>

          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-3 px-10 py-5 bg-primary text-black font-bold rounded-xl text-lg hover:bg-primary/90 transition-all hover:shadow-glow-green"
          >
            Launch SafeRoute AI Platform
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-border/50">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
              <Navigation size={14} className="text-primary" />
            </div>
            <span className="font-display font-bold text-white">SafeRoute AI</span>
          </div>
          <div className="text-sm text-slate-500">
            AI-Powered Temporal Safety Navigation · Real-time Risk Intelligence
          </div>
        </div>
      </footer>
    </div>
  );
}
