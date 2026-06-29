// ============================================
// CORE TYPES - SafeRoute AI
// ============================================

export type RiskLabel = 'safe' | 'moderate' | 'caution' | 'unsafe';

export interface Coordinate {
  lat: number;
  lng: number;
}

export interface RouteCoordinate {
  lat: number;
  lng: number;
  risk?: number;
}

// ============================================
// ROUTE TYPES
// ============================================

export interface RouteSegment {
  road_name: string;
  road_type: string;
  distance_km: number;
  risk_score: number;
  risk_label: RiskLabel;
  traffic_condition: string;
  coordinates?: RouteCoordinate[];
}

export interface RouteRecommendation {
  route_id: string;
  label: string; // "Route A", "Route B", "Route C"
  distance_km: number;
  travel_time_min: number;
  avg_risk: number;
  max_risk: number;
  confidence_score: number;
  safety_profile: string;
  explanation: string;
  coordinates: RouteCoordinate[];
  segments: RouteSegment[];
  risk_label: RiskLabel;
}

export interface RouteRequest {
  source: string;
  destination: string;
  hour: number;
  profile: 'safest' | 'fastest' | 'balanced';
}

export interface RouteResponse {
  routes: RouteRecommendation[];
  metadata: {
    generated_at: string;
    total_routes: number;
    analysis_time_ms: number;
  };
}

// ============================================
// WOMEN SAFETY TYPES
// ============================================

export interface WomenSafetyRequest {
  source: string;
  destination: string;
  hour: number;
}

export interface WomenSafetyResponse {
  women_safety_score: number;
  distance_km: number;
  travel_time_min: number;
  avg_risk: number;
  lighting_analysis: {
    score: number;
    label: string;
    dark_segments: number;
    well_lit_segments: number;
  };
  isolation_analysis: {
    score: number;
    label: string;
    isolated_segments: number;
    populated_segments: number;
  };
  safety_explanation: string;
  coordinates: RouteCoordinate[];
  risk_label: RiskLabel;
}

// ============================================
// EMERGENCY ESCAPE TYPES
// ============================================

export type EmergencyDestinationType =
  | 'police_station'
  | 'hospital'
  | 'metro_station'
  | 'public_area'
  | 'cctv_zone';

export interface EmergencyRoute {
  destination_type: EmergencyDestinationType;
  destination_name: string;
  distance_km: number;
  travel_time_min: number;
  risk_score: number;
  risk_label: RiskLabel;
  coordinates: RouteCoordinate[];
  destination_coordinates: Coordinate;
}

export interface EmergencyEscapeRequest {
  location: string;
  hour: number;
}

export interface EmergencyEscapeResponse {
  routes: EmergencyRoute[];
  nearest_safe_point: Coordinate;
}

// ============================================
// TIME MACHINE TYPES
// ============================================

export interface TimeSlotAnalysis {
  hour: number;
  label: string; // "Morning", "Afternoon", "Evening", "Night"
  risk_score: number;
  travel_time_min: number;
  route_cost: number;
  safety_label: RiskLabel;
}

export interface TimeMachineRequest {
  source: string;
  destination: string;
}

export interface TimeMachineResponse {
  hourly_analysis: TimeSlotAnalysis[];
  best_hour: number;
  worst_hour: number;
  summary: string;
}

// ============================================
// RISK FORECAST TYPES
// ============================================

export interface RiskForecastRequest {
  location: string;
  target_hour: number;
}

export interface HourlyForecast {
  hour: number;
  risk_score: number;
  risk_label: RiskLabel;
  confidence: number;
}

export interface RiskForecastResponse {
  current_risk: number;
  predicted_risk: number;
  trend: 'increasing' | 'decreasing' | 'stable';
  risk_label: RiskLabel;
  hourly_forecast: HourlyForecast[];
  prediction_confidence: number;
}

// ============================================
// INCIDENT TYPES
// ============================================

export type IncidentType =
  | 'accident'
  | 'flood'
  | 'crime'
  | 'road_closure'
  | 'construction'
  | 'event';

export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Incident {
  id: string;
  edge_id: string;
  incident_type: IncidentType;
  severity: IncidentSeverity;
  description: string;
  created_at: string;
  status: 'active' | 'resolved';
}

export interface CreateIncidentRequest {
  edge_id: string;
  incident_type: IncidentType;
  severity: IncidentSeverity;
  description: string;
}

export interface RemoveIncidentRequest {
  incident_id: string;
}

// ============================================
// SAFE & DANGER ZONE TYPES
// ============================================

export interface Zone {
  zone_id: string;
  zone_name: string;
  node_count: number;
  centroid: Coordinate;
  safety_label: 'safe' | 'danger';
  risk_score: number;
  area_km2?: number;
  nodes?: Coordinate[];
}

export interface ZonesResponse {
  zones: Zone[];
  total_count: number;
  generated_at: string;
}

// ============================================
// HEATMAP TYPES
// ============================================

export interface HeatmapPoint {
  lat: number;
  lng: number;
  intensity: number;
  risk_score: number;
}

export interface HeatmapResponse {
  points: HeatmapPoint[];
  safe_zones: Zone[];
  danger_zones: Zone[];
  hour: number;
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
}

// ============================================
// ANALYTICS TYPES
// ============================================

export interface AnalyticsResponse {
  total_routes_generated: number;
  average_route_risk: number;
  average_travel_time_min: number;
  average_confidence_score: number;
  safe_zones_count: number;
  danger_zones_count: number;
  active_incidents: number;
  risk_distribution: {
    safe: number;
    moderate: number;
    caution: number;
    unsafe: number;
  };
  travel_time_distribution: {
    bucket: string;
    count: number;
  }[];
  zone_risk_overview: {
    zone: string;
    risk: number;
  }[];
  recent_routes: {
    id: string;
    source: string;
    destination: string;
    risk: number;
    time: string;
  }[];
}

// ============================================
// ROUTE EXPLANATION TYPES
// ============================================

export interface RouteExplanation {
  selected_route: string;
  route_profile: string;
  avg_risk: number;
  travel_time_min: number;
  distance_km: number;
  risk_reduction_pct: number;
  major_roads_used: string[];
  high_risk_segments_avoided: string[];
  alternative_comparison: {
    route: string;
    risk: number;
    time: number;
  }[];
  confidence_score: number;
  ai_reasoning: string;
  reasoning_steps: string[];
}

// ============================================
// ROUTE SIMULATION TYPES
// ============================================

export interface SimulationSegment {
  minute: number;
  road_name: string;
  road_type: string;
  distance_km: number;
  risk_score: number;
  risk_label: RiskLabel;
  traffic_condition: string;
  coordinates: Coordinate;
}

export interface RouteSimulationResponse {
  total_time_min: number;
  total_distance_km: number;
  segments: SimulationSegment[];
  summary: string;
}

// ============================================
// UI STATE TYPES
// ============================================

export interface AppState {
  selectedRoute: RouteRecommendation | null;
  mapCenter: Coordinate;
  mapZoom: number;
  currentHour: number;
  sidebarOpen: boolean;
  activeIncidents: Incident[];
}
