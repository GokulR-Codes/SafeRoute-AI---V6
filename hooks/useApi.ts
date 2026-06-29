import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  routeService,
  womenSafetyService,
  emergencyService,
  timeMachineService,
  riskForecastService,
  incidentService,
  zoneService,
  heatmapService,
  analyticsService,
} from '@/services/api';
import type {
  RouteRequest,
  WomenSafetyRequest,
  EmergencyEscapeRequest,
  TimeMachineRequest,
  RiskForecastRequest,
  CreateIncidentRequest,
  RemoveIncidentRequest,
} from '@/types';

// Query keys
export const queryKeys = {
  routes: (req: RouteRequest) => ['routes', req] as const,
  womenSafety: (req: WomenSafetyRequest) => ['women-safety', req] as const,
  emergency: (req: EmergencyEscapeRequest) => ['emergency', req] as const,
  timeMachine: (req: TimeMachineRequest) => ['time-machine', req] as const,
  riskForecast: (req: RiskForecastRequest) => ['risk-forecast', req] as const,
  safeZones: ['safe-zones'] as const,
  dangerZones: ['danger-zones'] as const,
  heatmap: (hour?: number) => ['heatmap', hour] as const,
  analytics: ['analytics'] as const,
  routeExplanation: (routeId: string) => ['route-explanation', routeId] as const,
  routeSimulation: (routeId: string) => ['route-simulation', routeId] as const,
};

// ============================================
// ROUTE HOOKS
// ============================================

export function useRecommendRoutes(request: RouteRequest | null) {
  return useQuery({
    queryKey: request ? queryKeys.routes(request) : ['routes-disabled'],
    queryFn: () => routeService.recommendRoutes(request!),
    enabled: !!request,
    staleTime: 5 * 60 * 1000,
  });
}

export function useRouteExplanation(routeId: string | null) {
  return useQuery({
    queryKey: routeId ? queryKeys.routeExplanation(routeId) : ['explanation-disabled'],
    queryFn: () => routeService.getRouteExplanation(routeId!),
    enabled: !!routeId,
  });
}

export function useRouteSimulation(routeId: string | null) {
  return useQuery({
    queryKey: routeId ? queryKeys.routeSimulation(routeId) : ['simulation-disabled'],
    queryFn: () => routeService.getRouteSimulation(routeId!),
    enabled: !!routeId,
  });
}

// ============================================
// WOMEN SAFETY HOOKS
// ============================================

export function useWomenSafetyMutation() {
  return useMutation({
    mutationFn: (data: WomenSafetyRequest) => womenSafetyService.getSafeRoute(data),
  });
}

// ============================================
// EMERGENCY HOOKS
// ============================================

export function useEmergencyEscapeMutation() {
  return useMutation({
    mutationFn: (data: EmergencyEscapeRequest) => emergencyService.getEscapeRoutes(data),
  });
}

// ============================================
// TIME MACHINE HOOKS
// ============================================

export function useTimeMachineMutation() {
  return useMutation({
    mutationFn: (data: TimeMachineRequest) => timeMachineService.analyze(data),
  });
}

// ============================================
// RISK FORECAST HOOKS
// ============================================

export function useRiskForecastMutation() {
  return useMutation({
    mutationFn: (data: RiskForecastRequest) => riskForecastService.predict(data),
  });
}

// ============================================
// INCIDENT HOOKS
// ============================================

export function useCreateIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateIncidentRequest) => incidentService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

export function useRemoveIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RemoveIncidentRequest) => incidentService.remove(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

// ============================================
// ZONE HOOKS
// ============================================

export function useSafeZones() {
  return useQuery({
    queryKey: queryKeys.safeZones,
    queryFn: () => zoneService.getSafeZones(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useDangerZones() {
  return useQuery({
    queryKey: queryKeys.dangerZones,
    queryFn: () => zoneService.getDangerZones(),
    staleTime: 10 * 60 * 1000,
  });
}

// ============================================
// HEATMAP HOOKS
// ============================================

export function useHeatmap(hour?: number) {
  return useQuery({
    queryKey: queryKeys.heatmap(hour),
    queryFn: () => heatmapService.getHeatmap(hour),
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================
// ANALYTICS HOOKS
// ============================================

export function useAnalytics() {
  return useQuery({
    queryKey: queryKeys.analytics,
    queryFn: () => analyticsService.getAnalytics(),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}
