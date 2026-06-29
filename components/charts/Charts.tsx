'use client';

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const tooltipStyle = {
  backgroundColor: '#111827',
  border: '1px solid #1E293B',
  borderRadius: '8px',
  fontSize: '12px',
  color: '#E2E8F0',
};

const axisStyle = {
  fontSize: 11,
  fill: '#94A3B8',
};

// ============================================
// HOURLY RISK TREND LINE CHART
// ============================================
export function RiskTrendChart({ data, dataKey = 'risk_score', xKey = 'hour' }: {
  data: any[];
  dataKey?: string;
  xKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00E676" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#00E676" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey={xKey} tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke="#00E676"
          strokeWidth={2}
          fill="url(#riskGradient)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ============================================
// TRAVEL TIME TREND CHART
// ============================================
export function TravelTimeChart({ data, dataKey = 'travel_time_min', xKey = 'hour' }: {
  data: any[];
  dataKey?: string;
  xKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey={xKey} tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke="#00BFA5"
          strokeWidth={2}
          dot={{ fill: '#00BFA5', r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ============================================
// COST TREND CHART
// ============================================
export function CostTrendChart({ data, dataKey = 'route_cost', xKey = 'hour' }: {
  data: any[];
  dataKey?: string;
  xKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey={xKey} tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey={dataKey} fill="#FFC107" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================
// RISK DISTRIBUTION PIE CHART
// ============================================
const RISK_COLORS = ['#00E676', '#FFC107', '#FF9800', '#FF5252'];

export function RiskDistributionChart({ data }: {
  data: { name: string; value: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={4}
          dataKey="value"
        >
          {data.map((_, index) => (
            <Cell key={index} fill={RISK_COLORS[index % RISK_COLORS.length]} stroke="none" />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend
          verticalAlign="bottom"
          height={36}
          wrapperStyle={{ fontSize: '12px', color: '#94A3B8' }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ============================================
// TRAVEL TIME DISTRIBUTION BAR CHART
// ============================================
export function TravelTimeDistributionChart({ data }: {
  data: { bucket: string; count: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey="bucket" tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="count" fill="#00BFA5" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================
// ZONE RISK OVERVIEW HORIZONTAL BAR
// ============================================
export function ZoneRiskChart({ data }: {
  data: { zone: string; risk: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(240, data.length * 36)}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
        <XAxis type="number" domain={[0, 1]} tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis dataKey="zone" type="category" tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} width={100} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="risk" radius={[0, 4, 4, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={index}
              fill={
                entry.risk <= 0.25
                  ? '#00E676'
                  : entry.risk <= 0.5
                  ? '#FFC107'
                  : entry.risk <= 0.75
                  ? '#FF9800'
                  : '#FF5252'
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================
// RISK COMPARISON CHART (current vs predicted)
// ============================================
export function RiskComparisonChart({ data }: {
  data: { label: string; current: number; predicted: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey="label" tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: '12px', color: '#94A3B8' }} />
        <Bar dataKey="current" fill="#00BFA5" radius={[4, 4, 0, 0]} name="Current Risk" />
        <Bar dataKey="predicted" fill="#FFC107" radius={[4, 4, 0, 0]} name="Predicted Risk" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================
// HOURLY FORECAST AREA CHART
// ============================================
export function HourlyForecastChart({ data }: {
  data: { hour: number; risk_score: number; confidence: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFC107" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#FFC107" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey="hour" tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <YAxis tick={axisStyle} axisLine={{ stroke: '#1E293B' }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area
          type="monotone"
          dataKey="risk_score"
          stroke="#FFC107"
          strokeWidth={2}
          fill="url(#forecastGradient)"
          name="Risk Score"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
