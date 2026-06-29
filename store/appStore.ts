import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RouteRecommendation, Coordinate, Incident } from '@/types';

interface AppStore {
  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  // Map state
  mapCenter: Coordinate;
  mapZoom: number;
  setMapCenter: (center: Coordinate) => void;
  setMapZoom: (zoom: number) => void;

  // Current hour
  currentHour: number;
  setCurrentHour: (hour: number) => void;

  // Selected route
  selectedRoute: RouteRecommendation | null;
  setSelectedRoute: (route: RouteRecommendation | null) => void;

  // Active incidents
  activeIncidents: Incident[];
  addIncident: (incident: Incident) => void;
  removeIncident: (id: string) => void;

  // Last route request
  lastRouteSource: string;
  lastRouteDest: string;
  setLastRouteRequest: (source: string, dest: string) => void;
}

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      // Sidebar
      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      // Map state - default center (can be overridden by location)
      mapCenter: { lat: 28.6139, lng: 77.209 }, // Delhi default
      mapZoom: 12,
      setMapCenter: (center) => set({ mapCenter: center }),
      setMapZoom: (zoom) => set({ mapZoom: zoom }),

      // Current hour
      currentHour: new Date().getHours(),
      setCurrentHour: (hour) => set({ currentHour: hour }),

      // Selected route
      selectedRoute: null,
      setSelectedRoute: (route) => set({ selectedRoute: route }),

      // Incidents
      activeIncidents: [],
      addIncident: (incident) =>
        set((state) => ({ activeIncidents: [...state.activeIncidents, incident] })),
      removeIncident: (id) =>
        set((state) => ({
          activeIncidents: state.activeIncidents.filter((i) => i.id !== id),
        })),

      // Route request
      lastRouteSource: '',
      lastRouteDest: '',
      setLastRouteRequest: (source, dest) =>
        set({ lastRouteSource: source, lastRouteDest: dest }),
    }),
    {
      name: 'saferoute-storage',
      partialize: (state) => ({
        currentHour: state.currentHour,
        mapCenter: state.mapCenter,
        mapZoom: state.mapZoom,
        lastRouteSource: state.lastRouteSource,
        lastRouteDest: state.lastRouteDest,
      }),
    }
  )
);
