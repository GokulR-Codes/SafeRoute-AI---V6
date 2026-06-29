import axios from 'axios';
import type {
  RouteRequest,
  RouteResponse,
  WomenSafetyRequest,
  WomenSafetyResponse,
  EmergencyEscapeRequest,
  EmergencyEscapeResponse,
  TimeMachineRequest,
  TimeMachineResponse,
  RiskForecastRequest,
  RiskForecastResponse,
  CreateIncidentRequest,
  RemoveIncidentRequest,
  Incident,
  ZonesResponse,
  HeatmapResponse,
  AnalyticsResponse,
  RouteExplanation,
  RouteSimulationResponse,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor
apiClient.interceptors.request.use((config) => {
  return config;
});

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ============================================
// ROUTE SERVICES
// ============================================

export const routeService = {
  recommendRoutes: async (data: RouteRequest): Promise<RouteResponse> => {
    const response = await apiClient.post('/recommend_routes', data);
    return response.data;
  },

  getRouteExplanation: async (routeId: string): Promise<RouteExplanation> => {
    const response = await apiClient.get('/route_explanation', {
      params: { route_id: routeId },
    });
    return response.data;
  },

  getRouteSimulation: async (routeId: string): Promise<RouteSimulationResponse> => {
    const response = await apiClient.get('/route_simulation', {
      params: { route_id: routeId },
    });
    return response.data;
  },
};

// ============================================
// WOMEN SAFETY SERVICE
// ============================================

export const womenSafetyService = {
  getSafeRoute: async (data: WomenSafetyRequest): Promise<WomenSafetyResponse> => {
    const response = await apiClient.post('/women_safe_route', data);
    return response.data;
  },
};

// ============================================
// EMERGENCY SERVICE
// ============================================

export const emergencyService = {
  getEscapeRoutes: async (data: EmergencyEscapeRequest): Promise<EmergencyEscapeResponse> => {
    const response = await apiClient.post('/emergency_escape', data);
    return response.data;
  },
};

// ============================================
// TIME MACHINE SERVICE
// ============================================

export const timeMachineService = {
  analyze: async (data: TimeMachineRequest): Promise<TimeMachineResponse> => {
    const response = await apiClient.post('/time_machine', data);
    return response.data;
  },
};

// ============================================
// RISK FORECAST SERVICE
// ============================================

export const riskForecastService = {
  predict: async (data: RiskForecastRequest): Promise<RiskForecastResponse> => {
    const response = await apiClient.post('/predict_future_risk', data);
    return response.data;
  },
};

// ============================================
// INCIDENT SERVICE
// ============================================

export const incidentService = {
  create: async (data: CreateIncidentRequest): Promise<Incident> => {
    const response = await apiClient.post('/incident/create', data);
    return response.data;
  },

  remove: async (data: RemoveIncidentRequest): Promise<void> => {
    await apiClient.post('/incident/remove', data);
  },
};

// ============================================
// ZONE SERVICES
// ============================================

export const zoneService = {
  getSafeZones: async (): Promise<ZonesResponse> => {
    const response = await apiClient.get('/safe_zones');
    return response.data;
  },

  getDangerZones: async (): Promise<ZonesResponse> => {
    const response = await apiClient.get('/danger_zones');
    return response.data;
  },
};

// ============================================
// HEATMAP SERVICE
// ============================================

export const heatmapService = {
  getHeatmap: async (hour?: number): Promise<HeatmapResponse> => {
    const response = await apiClient.get('/heatmap', {
      params: hour !== undefined ? { hour } : {},
    });
    return response.data;
  },
};

// ============================================
// ANALYTICS SERVICE
// ============================================

export const analyticsService = {
  getAnalytics: async (): Promise<AnalyticsResponse> => {
    const response = await apiClient.get('/analytics');
    return response.data;
  },
};
