# SafeRoute AI — Frontend

AI-Powered Temporal Safety Navigation System. Next.js 15 / React 19 / TypeScript frontend, fully wired to the SafeRoute AI backend engine.

## Setup

```bash
npm install --legacy-peer-deps
cp .env.example .env.local
# edit .env.local with your backend URL and Mapbox token
npm run dev
```

## Environment Variables

- `NEXT_PUBLIC_API_URL` — base URL of the SafeRoute backend (default `http://localhost:8000`)
- `NEXT_PUBLIC_MAPBOX_TOKEN` — Mapbox GL JS access token (required for all map views)

## Backend Endpoints Expected

- `POST /recommend_routes`
- `POST /women_safe_route`
- `POST /emergency_escape`
- `POST /time_machine`
- `POST /predict_future_risk`
- `POST /incident/create`
- `POST /incident/remove`
- `GET /safe_zones`
- `GET /danger_zones`
- `GET /heatmap`
- `GET /analytics`
- `GET /route_explanation`
- `GET /route_simulation`

## Structure

- `app/` — pages (landing + 11 app routes)
- `components/ui` — base design system primitives
- `components/map` — Mapbox layers (routes, markers, heatmap, zones, legend)
- `components/charts` — Recharts visualizations
- `components/layout` — shell, sidebar, top nav
- `services/api.ts` — Axios client + endpoint services
- `hooks/useApi.ts` — React Query hooks
- `store/appStore.ts` — Zustand global state
- `types/index.ts` — all TypeScript interfaces

## Build

```bash
npm run build
npm start
```

Verified production build passes with all 14 routes statically generated.
