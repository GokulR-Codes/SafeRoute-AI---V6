/**
 * ============================================================================
 * SafeRoute-AI  |  MongoDB Schema Definitions
 * Database: SAFEROUTE_AI
 * ============================================================================
 *
 * Collections defined in this file:
 *   1.  RiskSegments          — core road-segment risk records (zone CSVs)
 *   2.  GraphNodes            — graph routing nodes
 *   3.  GraphEdges            — directed graph edges with static metadata
 *   4.  HourlyEdgeWeights     — per-edge, per-hour dynamic risk weights
 *   5.  ZoneSummary           — per-zone aggregated statistics
 *   6.  CityHourlyProfile     — city-wide hourly risk statistics
 *   7.  ZoneHourlyRisk        — per zone-type hourly risk sweep
 *   8.  TopRiskSegments       — pre-computed high-risk hotspot segments
 *   9.  FactorContributions   — risk factor weight/contribution breakdown
 *  10.  HourlyRiskSweep       — city-wide hourly sweep summary
 *  11.  CorrelationValidation — correlation checks between risk metrics
 *  12.  IncidentLayer         — live/injected incidents on edges
 *  13.  RouteCache            — cached route results per profile
 *  14.  PoliceStations        — reference POI: police stations
 *  15.  Hospitals             — reference POI: hospitals
 *  16.  SafeHavens            — snapped safe-haven graph nodes
 *
 * Run these validator commands via mongosh:
 *   mongosh "your_mongo_uri" --file db_schemas.js
 * ============================================================================
 */

// ─────────────────────────────────────────────────────────────────────────────
// Helper: drop-safe collection creation
// ─────────────────────────────────────────────────────────────────────────────
function createCollection(name, options) {
  try {
    db.createCollection(name, options);
    print(`✅  Created collection: ${name}`);
  } catch (e) {
    if (e.codeName === "NamespaceExists") {
      print(`⚠️   Collection already exists (skipped): ${name}`);
    } else {
      throw e;
    }
  }
}

const db = db.getSiblingDB("SAFEROUTE_AI");

// ============================================================================
// 1. RiskSegments
// ============================================================================
// Source: central_bangalore_risk.csv, north_bangalore_risk.csv, etc. (8 zone files)
// One document = one road segment with all 34 risk features.
// ============================================================================
createCollection("RiskSegments", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["zone", "lat", "lng", "road_risk_score"],
      properties: {
        // ── Spatial ──────────────────────────────────────────────────────
        zone: {
          bsonType: "string",
          description: "Zone label e.g. 'CENTRAL BANGALORE', 'NORTH BANGALORE'",
          enum: [
            "CENTRAL BANGALORE", "NORTH BANGALORE", "SOUTH BANGALORE",
            "EAST BANGALORE", "WEST BANGALORE",
            "SOUTHEAST / IT CORRIDOR", "AIRPORT / PERIPHERAL",
            "LOGISTICS / HIGH-TRAFFIC"
          ]
        },
        direction: { bsonType: "string", description: "e.g. 'Bi-directional', 'One-way'" },
        lat: { bsonType: ["double", "null"], description: "WGS-84 latitude" },
        lng: { bsonType: ["double", "null"], description: "WGS-84 longitude" },
        location: {
          bsonType: ["object", "null"],
          description: "GeoJSON Point — {type:'Point', coordinates:[lng, lat]}",
          required: ["type", "coordinates"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array",  minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },

        // ── Road identity ─────────────────────────────────────────────────
        source_area:      { bsonType: "string", description: "Origin area/neighbourhood" },
        destination_area: { bsonType: "string", description: "Destination area/neighbourhood" },
        road_name:        { bsonType: ["string", "null"] },
        road_type: {
          bsonType: "string",
          enum: ["motorway","motorway_link","trunk","trunk_link","highway",
                 "primary","primary_link","secondary","secondary_link",
                 "tertiary","tertiary_link","residential","living_street",
                 "service","unclassified","busway","road","connector",
                 "arterial_connector","healed_connector"]
        },
        highway_type:    { bsonType: ["string", "null"] },
        junction_type:   { bsonType: ["string", "null"] },
        road_width_estimate: { bsonType: ["string", "null"], description: "e.g. '7.5m'" },

        // ── Traffic & Connectivity ────────────────────────────────────────
        speed_limit:              { bsonType: ["double", "null"], minimum: 0 },
        traffic_signal_density:   { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        intersection_density:     { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        adjacency_count:          { bsonType: ["double", "int", "null"], minimum: 0 },

        // ── Urban density factors ─────────────────────────────────────────
        commercial_density:   { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        nightlife_density:    { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        hospital_density:     { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        poi_density:          { bsonType: ["double", "null"], minimum: 0, maximum: 1 },

        // ── Safety infrastructure ─────────────────────────────────────────
        police_station_distance:  { bsonType: ["double", "null"], minimum: 0,
                                    description: "Normalised distance (0-1)" },
        cctv_density_estimate:    { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        lighting_score:           { bsonType: ["double", "null"], minimum: 0, maximum: 1 },

        // ── Core risk scores (0-1 range unless stated) ────────────────────
        crime_score:          { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        activity_score:       { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        event_frequency:      { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        infrastructure_score: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        connectivity_score:   { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        isolated_area_score:  { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        road_risk_score:      { bsonType: ["double", "null"], minimum: 0, maximum: 1,
                                description: "Core road risk [0-1]" },

        // ── Environmental / temporal ──────────────────────────────────────
        flood_risk:              { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        weather_exposure_score:  { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        time_risk:               { bsonType: ["double", "null"], minimum: 0, maximum: 1 },

        // ── Travel estimates ──────────────────────────────────────────────
        travel_time_estimate: { bsonType: ["double", "null"], minimum: 0,
                                description: "Minutes" },
        congestion_score:     { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
      }
    }
  },
  validationAction: "warn"
});

db.RiskSegments.createIndex({ location: "2dsphere" });
db.RiskSegments.createIndex({ zone: 1, road_risk_score: -1 });
db.RiskSegments.createIndex({ source_area: 1, destination_area: 1 });
db.RiskSegments.createIndex({ crime_score: -1 });
db.RiskSegments.createIndex({ isolated_area_score: -1 });
print("  → Indexes on RiskSegments created");

// ============================================================================
// 2. GraphNodes
// ============================================================================
// Source: ENGINE/datasets/graph_nodes.csv
// Columns: node_id, lat, lng (+ adjacency_count, connectivity_score from v8)
// ============================================================================
createCollection("GraphNodes", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["node_id", "lat", "lng"],
      properties: {
        node_id:   { bsonType: ["int", "long"], description: "Unique integer node ID" },
        lat:       { bsonType: "double" },
        lng:       { bsonType: "double" },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
        zone:               { bsonType: ["string", "null"] },
        source_area:        { bsonType: ["string", "null"] },
        adjacency_count:    { bsonType: ["int", "null"], minimum: 0 },
        connectivity_score: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        // v8 additions
        is_dead_end:        { bsonType: ["bool", "null"] },
        is_merged:          { bsonType: ["bool", "null"],
                              description: "True if node was spatially merged (8m radius)" },
        merged_into:        { bsonType: ["int", "null"],
                              description: "Parent node_id if this node was merged away" },
      }
    }
  },
  validationAction: "warn"
});

db.GraphNodes.createIndex({ node_id: 1 }, { unique: true });
db.GraphNodes.createIndex({ location: "2dsphere" });
db.GraphNodes.createIndex({ zone: 1 });
db.GraphNodes.createIndex({ source_area: 1 });
print("  → Indexes on GraphNodes created");

// ============================================================================
// 3. GraphEdges
// ============================================================================
// Source: ENGINE/datasets/graph_edges.csv  (static + risk columns)
// ============================================================================
createCollection("GraphEdges", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["edge_id", "u", "v"],
      properties: {
        edge_id:          { bsonType: "string", description: "e.g. 'EDGE_0_42909'" },
        // Graph topology (v6 CSV uses u/v; v8 renames to source_node/destination_node)
        u:                { bsonType: ["int", "long"], description: "Source node_id" },
        v:                { bsonType: ["int", "long"], description: "Destination node_id" },
        source_node:      { bsonType: ["int", "long", "null"] },
        destination_node: { bsonType: ["int", "long", "null"] },

        // Centroid of segment
        lat: { bsonType: ["double", "null"] },
        lng: { bsonType: ["double", "null"] },

        // Road identity
        road_name:        { bsonType: ["string", "null"] },
        road_type:        { bsonType: ["string", "null"] },
        highway_type:     { bsonType: ["string", "null"] },
        direction:        { bsonType: ["string", "null"] },
        zone:             { bsonType: ["string", "null"] },
        zone_type:        { bsonType: ["string", "null"] },
        source_area:      { bsonType: ["string", "null"] },
        destination_area: { bsonType: ["string", "null"] },

        // Static geometry/capacity (v8 outputs)
        static_distance_km:       { bsonType: ["double", "null"], minimum: 0 },
        static_travel_time_min:   { bsonType: ["double", "null"], minimum: 0 },
        bearing:                  { bsonType: ["double", "null"], minimum: 0, maximum: 360 },
        geometry_length:          { bsonType: ["double", "null"], minimum: 0 },
        road_curvature:           { bsonType: ["double", "null"] },
        geometry_polyline:        { bsonType: ["string", "null"],
                                    description: "JSON string [[lat,lng], ...]" },

        // Elevation (Phase 3, v8)
        elevation_m:    { bsonType: ["double", "null"] },
        slope_percent:  { bsonType: ["double", "null"] },
        bridge_flag:    { bsonType: ["int", "bool", "null"] },
        flyover_flag:   { bsonType: ["int", "bool", "null"] },
        underpass_flag: { bsonType: ["int", "bool", "null"] },

        // Capacity (Phase 4, v8)
        lane_count:            { bsonType: ["int", "null"] },
        capacity_score:        { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        road_importance_score: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        capacity_weight:       { bsonType: ["double", "null"] },

        // Turn restriction (Phase 2, v8 — stored on edge for A* lookup)
        turn_penalty:   { bsonType: ["double", "null"], minimum: 0, maximum: 1 },

        // Pre-computed static risk composite (from graph_edges.csv)
        road_width_estimate:       { bsonType: ["string", "double", "null"] },
        speed_limit:               { bsonType: ["double", "null"] },
        traffic_signal_density:    { bsonType: ["double", "null"] },
        intersection_density:      { bsonType: ["double", "null"] },
        commercial_density:        { bsonType: ["double", "null"] },
        nightlife_density:         { bsonType: ["double", "null"] },
        hospital_density:          { bsonType: ["double", "null"] },
        police_station_distance:   { bsonType: ["double", "null"] },
        cctv_density_estimate:     { bsonType: ["double", "null"] },
        lighting_score:            { bsonType: ["double", "null"] },
        crime_score:               { bsonType: ["double", "null"] },
        activity_score:            { bsonType: ["double", "null"] },
        event_frequency:           { bsonType: ["double", "null"] },
        infrastructure_score:      { bsonType: ["double", "null"] },
        connectivity_score:        { bsonType: ["double", "null"] },
        isolated_area_score:       { bsonType: ["double", "null"] },
        road_risk_score:           { bsonType: ["double", "null"] },
        travel_time_estimate:      { bsonType: ["double", "null"] },
        congestion_score:          { bsonType: ["double", "null"] },
        flood_risk:                { bsonType: ["double", "null"] },
        weather_exposure_score:    { bsonType: ["double", "null"] },
        poi_density:               { bsonType: ["double", "null"] },
        time_risk:                 { bsonType: ["double", "null"] },
        adjacency_count:           { bsonType: ["double", "int", "null"] },
        static_component:          { bsonType: ["double", "null"] },
        graph_component:           { bsonType: ["double", "null"] },

        // Connector flags (v8 stitching)
        edge_source: {
          bsonType: ["string", "null"],
          description: "One of: 'dataset', 'CONN', 'HEAL', 'HEALR'"
        },
      }
    }
  },
  validationAction: "warn"
});

db.GraphEdges.createIndex({ edge_id: 1 }, { unique: true });
db.GraphEdges.createIndex({ u: 1, v: 1 });
db.GraphEdges.createIndex({ source_node: 1, destination_node: 1 });
db.GraphEdges.createIndex({ zone: 1 });
db.GraphEdges.createIndex({ road_type: 1 });
db.GraphEdges.createIndex({ road_risk_score: -1 });
print("  → Indexes on GraphEdges created");

// ============================================================================
// 4. HourlyEdgeWeights
// ============================================================================
// Source: ENGINE/datasets/hourly_edge_weights.csv
// Flattened format: one document per (edge_id × hour) pair.
// The raw CSV stores 24 columns (hour_00…hour_23); we store normalized docs.
// ============================================================================
createCollection("HourlyEdgeWeights", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["edge_id", "hour"],
      properties: {
        edge_id: { bsonType: "string" },
        hour:    { bsonType: "int", minimum: 0, maximum: 23,
                   description: "Hour of day (0–23)" },

        // Core weight fields (v8 routing engine)
        final_edge_weight:      { bsonType: ["double", "null"], minimum: 0 },
        final_risk_score:       { bsonType: ["double", "null"], minimum: 0 },
        congestion_score:       { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        time_risk:              { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        weather_exposure_score: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        dynamic_risk_score:     { bsonType: ["double", "null"], minimum: 0 },

        // Extended columns (built by Risk Engine v6.1)
        lighting_dark_risk:  { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        isolated_area_score: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        crime_score:         { bsonType: ["double", "null"], minimum: 0, maximum: 1 },

        // Alternative: raw 24-column format for the simple CSV import path
        // (mutually exclusive with per-row hour format above)
        hour_00: { bsonType: ["double", "null"] },
        hour_01: { bsonType: ["double", "null"] },
        hour_02: { bsonType: ["double", "null"] },
        hour_03: { bsonType: ["double", "null"] },
        hour_04: { bsonType: ["double", "null"] },
        hour_05: { bsonType: ["double", "null"] },
        hour_06: { bsonType: ["double", "null"] },
        hour_07: { bsonType: ["double", "null"] },
        hour_08: { bsonType: ["double", "null"] },
        hour_09: { bsonType: ["double", "null"] },
        hour_10: { bsonType: ["double", "null"] },
        hour_11: { bsonType: ["double", "null"] },
        hour_12: { bsonType: ["double", "null"] },
        hour_13: { bsonType: ["double", "null"] },
        hour_14: { bsonType: ["double", "null"] },
        hour_15: { bsonType: ["double", "null"] },
        hour_16: { bsonType: ["double", "null"] },
        hour_17: { bsonType: ["double", "null"] },
        hour_18: { bsonType: ["double", "null"] },
        hour_19: { bsonType: ["double", "null"] },
        hour_20: { bsonType: ["double", "null"] },
        hour_21: { bsonType: ["double", "null"] },
        hour_22: { bsonType: ["double", "null"] },
        hour_23: { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.HourlyEdgeWeights.createIndex({ edge_id: 1, hour: 1 }, { unique: true });
db.HourlyEdgeWeights.createIndex({ hour: 1, final_risk_score: -1 });
print("  → Indexes on HourlyEdgeWeights created");

// ============================================================================
// 5. ZoneSummary
// ============================================================================
// Source: ENGINE/outputs/saferoute_v6_zone_summary.csv
// Aggregated per-zone statistics produced by the Risk Engine.
// ============================================================================
createCollection("ZoneSummary", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["zone"],
      properties: {
        zone:      { bsonType: "string" },
        direction: { bsonType: ["string", "null"] },
        segments:  { bsonType: ["int", "null"], minimum: 0 },

        // Risk distribution
        risk_mean:   { bsonType: ["double", "null"] },
        risk_median: { bsonType: ["double", "null"] },
        risk_p95:    { bsonType: ["double", "null"] },
        risk_max:    { bsonType: ["double", "null"] },

        // Contextual & confidence
        contextual_mean: { bsonType: ["double", "null"] },
        confidence_mean: { bsonType: ["double", "null"] },
        uncertainty_mean:{ bsonType: ["double", "null"] },

        // Factor means
        crime_mean:        { bsonType: ["double", "null"] },
        lighting_mean:     { bsonType: ["double", "null"] },
        police_mean:       { bsonType: ["double", "null"] },
        cctv_mean:         { bsonType: ["double", "null"] },
        congestion_mean:   { bsonType: ["double", "null"] },
        travel_time_mean:  { bsonType: ["double", "null"] },
        connectivity_mean: { bsonType: ["double", "null"] },
        isolation_mean:    { bsonType: ["double", "null"] },
        road_risk_mean:    { bsonType: ["double", "null"] },
        behav_adj_mean:    { bsonType: ["double", "null"] },
        poi_interaction_mean: { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.ZoneSummary.createIndex({ zone: 1, direction: 1 }, { unique: true });
db.ZoneSummary.createIndex({ risk_mean: -1 });
print("  → Indexes on ZoneSummary created");

// ============================================================================
// 6. CityHourlyProfile
// ============================================================================
// Source: ENGINE/outputs/city_hourly_profile.csv
// City-wide risk statistics aggregated per hour.
// ============================================================================
createCollection("CityHourlyProfile", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["hour"],
      properties: {
        hour:      { bsonType: "int", minimum: 0, maximum: 23 },
        mean_risk: { bsonType: ["double", "null"] },
        p25_risk:  { bsonType: ["double", "null"] },
        p75_risk:  { bsonType: ["double", "null"] },
        max_risk:  { bsonType: ["double", "null"] },
        min_risk:  { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.CityHourlyProfile.createIndex({ hour: 1 }, { unique: true });
print("  → Indexes on CityHourlyProfile created");

// ============================================================================
// 7. ZoneHourlyRisk
// ============================================================================
// Source: ENGINE/outputs/zone_hourly_risk.csv
// Per-zone-type hourly risk averages (24-column pivoted).
// ============================================================================
createCollection("ZoneHourlyRisk", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["zone_type"],
      properties: {
        zone_type: { bsonType: "string",
                     description: "e.g. 'Airport Zone', 'IT Corridor', 'Industrial Zone'" },
        hour_00: { bsonType: ["double", "null"] },
        hour_01: { bsonType: ["double", "null"] },
        hour_02: { bsonType: ["double", "null"] },
        hour_03: { bsonType: ["double", "null"] },
        hour_04: { bsonType: ["double", "null"] },
        hour_05: { bsonType: ["double", "null"] },
        hour_06: { bsonType: ["double", "null"] },
        hour_07: { bsonType: ["double", "null"] },
        hour_08: { bsonType: ["double", "null"] },
        hour_09: { bsonType: ["double", "null"] },
        hour_10: { bsonType: ["double", "null"] },
        hour_11: { bsonType: ["double", "null"] },
        hour_12: { bsonType: ["double", "null"] },
        hour_13: { bsonType: ["double", "null"] },
        hour_14: { bsonType: ["double", "null"] },
        hour_15: { bsonType: ["double", "null"] },
        hour_16: { bsonType: ["double", "null"] },
        hour_17: { bsonType: ["double", "null"] },
        hour_18: { bsonType: ["double", "null"] },
        hour_19: { bsonType: ["double", "null"] },
        hour_20: { bsonType: ["double", "null"] },
        hour_21: { bsonType: ["double", "null"] },
        hour_22: { bsonType: ["double", "null"] },
        hour_23: { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.ZoneHourlyRisk.createIndex({ zone_type: 1 }, { unique: true });
print("  → Indexes on ZoneHourlyRisk created");

// ============================================================================
// 8. TopRiskSegments
// ============================================================================
// Source: ENGINE/outputs/saferoute_v6_top_risk_segments.csv
// Pre-computed highest-risk segments for dashboard/alert purposes.
// ============================================================================
createCollection("TopRiskSegments", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["zone", "lat", "lng", "final_risk_score"],
      properties: {
        zone:             { bsonType: "string" },
        lat:              { bsonType: "double" },
        lng:              { bsonType: "double" },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
        final_risk_score:   { bsonType: "double", minimum: 0, maximum: 100 },
        contextual_risk:    { bsonType: ["double", "null"] },
        confidence_score:   { bsonType: ["double", "null"] },
        uncertainty_level:  { bsonType: ["double", "null"] },
        risk_band: {
          bsonType: ["string", "null"],
          enum: ["Low", "Moderate", "High", "Critical", null]
        },
        road_risk_score:    { bsonType: ["double", "null"] },
        congestion_score:   { bsonType: ["double", "null"] },
        travel_time_estimate: { bsonType: ["double", "null"] },
        score_crime:        { bsonType: ["double", "null"] },
        score_lighting:     { bsonType: ["double", "null"] },
        score_police:       { bsonType: ["double", "null"] },
        isolated_area_score:{ bsonType: ["double", "null"] },
        connectivity_score: { bsonType: ["double", "null"] },
        behavioural_adj:    { bsonType: ["double", "null"] },
        poi_interaction:    { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.TopRiskSegments.createIndex({ location: "2dsphere" });
db.TopRiskSegments.createIndex({ final_risk_score: -1 });
db.TopRiskSegments.createIndex({ zone: 1, final_risk_score: -1 });
print("  → Indexes on TopRiskSegments created");

// ============================================================================
// 9. FactorContributions
// ============================================================================
// Source: ENGINE/outputs/saferoute_v6_factor_contributions.csv
// Risk factor weights and their mean contributions to final_risk_score.
// ============================================================================
createCollection("FactorContributions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["factor"],
      properties: {
        factor:       { bsonType: "string",
                        description: "e.g. 'crime', 'lighting', 'police', 'cctv'" },
        mean_score:   { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        base_weight:  { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        contribution: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        // Optional snapshot metadata
        snapshot_ts: { bsonType: ["date", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.FactorContributions.createIndex({ factor: 1 }, { unique: true });
print("  → Indexes on FactorContributions created");

// ============================================================================
// 10. HourlyRiskSweep
// ============================================================================
// Source: ENGINE/outputs/saferoute_v6_hourly_sweep.csv
// City-wide hourly sweep with time context labels and distribution stats.
// ============================================================================
createCollection("HourlyRiskSweep", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["hour"],
      properties: {
        hour:         { bsonType: "int", minimum: 0, maximum: 23 },
        time_context: { bsonType: ["string", "null"],
                        description: "e.g. 'night_deep', 'morning_peak', 'daytime'" },
        risk_mean:      { bsonType: ["double", "null"] },
        risk_std:       { bsonType: ["double", "null"] },
        risk_p90:       { bsonType: ["double", "null"] },
        risk_max:       { bsonType: ["double", "null"] },
        contextual_mean:  { bsonType: ["double", "null"] },
        congestion_mean:  { bsonType: ["double", "null"] },
        travel_time_mean: { bsonType: ["double", "null"] },
        connectivity_mean:{ bsonType: ["double", "null"] },
        isolation_mean:   { bsonType: ["double", "null"] },
        confidence_mean:  { bsonType: ["double", "null"] },
        uncertainty_mean: { bsonType: ["double", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.HourlyRiskSweep.createIndex({ hour: 1 }, { unique: true });
print("  → Indexes on HourlyRiskSweep created");

// ============================================================================
// 11. CorrelationValidation
// ============================================================================
// Source: ENGINE/outputs/saferoute_v6_correlation_validation.csv
// Pearson-r checks between risk factor pairs — QA/audit log.
// ============================================================================
createCollection("CorrelationValidation", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["check", "col_a", "col_b"],
      properties: {
        check:     { bsonType: "string",
                     description: "Human-readable description of correlation check" },
        col_a:     { bsonType: "string" },
        col_b:     { bsonType: "string" },
        pearson_r: { bsonType: ["double", "null"], minimum: -1, maximum: 1 },
        expected:  { bsonType: ["string", "null"],
                     description: "'+' or '-' indicating expected sign" },
        status:    { bsonType: ["string", "null"],
                     enum: ["PASS", "FAIL", null] },
        run_ts:    { bsonType: ["date", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.CorrelationValidation.createIndex({ check: 1 });
db.CorrelationValidation.createIndex({ status: 1 });
print("  → Indexes on CorrelationValidation created");

// ============================================================================
// 12. IncidentLayer
// ============================================================================
// Source: ENGINE/outputs/incident_layer.csv  +  Phase 23 live injections
// Live / user-reported incidents mapped to graph edges.
// ============================================================================
createCollection("IncidentLayer", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["edge_id", "type"],
      properties: {
        edge_id:  { bsonType: "string" },
        type: {
          bsonType: "string",
          enum: ["Accident", "Flood", "Crime", "Road Closure",
                 "Construction", "Event", "crime_spike", "road_closure",
                 "accident", "flood", "event", "construction"]
        },
        severity:         { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        hazard_penalty:   { bsonType: ["double", "null"], minimum: 0 },
        description:      { bsonType: ["string", "null"] },
        active:           { bsonType: ["bool", "int", "null"] },
        reported_hour:    { bsonType: ["int", "null"], minimum: 0, maximum: 23 },
        reported_at:      { bsonType: ["date", "null"] },
        expires_at:       { bsonType: ["date", "null"] },
        lat:              { bsonType: ["double", "null"] },
        lng:              { bsonType: ["double", "null"] },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
      }
    }
  },
  validationAction: "warn"
});

db.IncidentLayer.createIndex({ edge_id: 1 });
db.IncidentLayer.createIndex({ location: "2dsphere" });
db.IncidentLayer.createIndex({ active: 1, type: 1 });
db.IncidentLayer.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });
print("  → Indexes on IncidentLayer created");

// ============================================================================
// 13. RouteCache
// ============================================================================
// Stores computed A* route results for fast re-serving.
// Key: (source_node, destination_node, hour, profile)
// ============================================================================
createCollection("RouteCache", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["source_node", "destination_node", "profile"],
      properties: {
        source_node:      { bsonType: ["int", "long"] },
        destination_node: { bsonType: ["int", "long"] },
        hour:             { bsonType: ["int", "null"], minimum: 0, maximum: 23 },
        profile: {
          bsonType: "string",
          enum: ["default", "women", "fastest", "balanced",
                 "FASTEST", "SAFEST", "BALANCED", "WOMEN_SAFE", "EMERGENCY"]
        },
        path:       { bsonType: ["array", "null"],
                      description: "Ordered list of node_ids" },
        edge_path:  { bsonType: ["array", "null"],
                      description: "Ordered list of edge_ids" },
        cost:       { bsonType: ["double", "null"] },
        metrics: {
          bsonType: ["object", "null"],
          properties: {
            total_distance_km:     { bsonType: ["double", "null"] },
            total_travel_time_min: { bsonType: ["double", "null"] },
            average_risk:          { bsonType: ["double", "null"] },
            maximum_risk:          { bsonType: ["double", "null"] },
            average_congestion:    { bsonType: ["double", "null"] },
            weather_exposure:      { bsonType: ["double", "null"] },
            node_count:            { bsonType: ["int", "null"] },
            edge_count:            { bsonType: ["int", "null"] },
            average_lighting_dark_risk: { bsonType: ["double", "null"] },
            average_isolation:     { bsonType: ["double", "null"] },
          }
        },
        coordinates: { bsonType: ["array", "null"],
                       description: "[[lat,lng], ...] for map rendering" },
        explanation: { bsonType: ["object", "null"] },
        confidence_score: { bsonType: ["int", "null"], minimum: 0, maximum: 100 },
        created_at:  { bsonType: ["date", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.RouteCache.createIndex(
  { source_node: 1, destination_node: 1, hour: 1, profile: 1 },
  { unique: true }
);
db.RouteCache.createIndex(
  { created_at: 1 },
  { expireAfterSeconds: 3600, name: "route_cache_ttl_1h" }
);
print("  → Indexes on RouteCache created");

// ============================================================================
// 14. PoliceStations
// ============================================================================
// Reference POI: hardcoded in safe_route_engine_v6.py & routing_engine_v8.py
// Stored in MongoDB so the API can serve them for map overlays.
// ============================================================================
createCollection("PoliceStations", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "lat", "lng"],
      properties: {
        name:     { bsonType: "string" },
        lat:      { bsonType: "double" },
        lng:      { bsonType: "double" },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
        nearest_node_id: { bsonType: ["int", "null"],
                           description: "Snapped graph node_id (populated after graph load)" },
        zone:   { bsonType: ["string", "null"] },
        active: { bsonType: ["bool", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.PoliceStations.createIndex({ location: "2dsphere" });
db.PoliceStations.createIndex({ name: 1 }, { unique: true });
print("  → Indexes on PoliceStations created");

// Seed from engine constants
const policeData = [
  { name: "Hebbal PS",           lat: 13.0360, lng: 77.5970, zone: "North Bangalore" },
  { name: "RT Nagar PS",         lat: 13.0220, lng: 77.5975, zone: "North Bangalore" },
  { name: "Yelahanka PS",        lat: 13.1006, lng: 77.5960, zone: "North Bangalore" },
  { name: "Byatarayanapura PS",  lat: 13.0590, lng: 77.5600, zone: "North Bangalore" },
  { name: "Devanahalli PS",      lat: 13.2470, lng: 77.7110, zone: "Airport / Peripheral" },
  { name: "Jakkur PS",           lat: 13.0715, lng: 77.5880, zone: "North Bangalore" },
  { name: "Nagawara PS",         lat: 13.0450, lng: 77.6250, zone: "North Bangalore" },
  { name: "Rajajinagar PS",      lat: 12.9840, lng: 77.5510, zone: "West Bangalore" },
  { name: "Malleswaram PS",      lat: 12.9990, lng: 77.5720, zone: "West Bangalore" },
  { name: "Majestic PS",         lat: 12.9770, lng: 77.5720, zone: "West Bangalore" },
  { name: "Magadi Road PS",      lat: 12.9640, lng: 77.5170, zone: "West Bangalore" },
  { name: "Kengeri PS",          lat: 12.9149, lng: 77.4840, zone: "West Bangalore" },
  { name: "Indiranagar PS",      lat: 12.9792, lng: 77.6388, zone: "East Bangalore" },
  { name: "Whitefield PS",       lat: 12.9698, lng: 77.7500, zone: "East Bangalore" },
  { name: "KR Puram PS",         lat: 13.0020, lng: 77.6960, zone: "East Bangalore" },
  { name: "Marathahalli PS",     lat: 12.9591, lng: 77.7011, zone: "East Bangalore" },
  { name: "HAL PS",              lat: 12.9634, lng: 77.6596, zone: "East Bangalore" },
  { name: "Koramangala PS",      lat: 12.9293, lng: 77.6210, zone: "South Bangalore" },
  { name: "BTM Layout PS",       lat: 12.9126, lng: 77.6101, zone: "South Bangalore" },
  { name: "JP Nagar PS",         lat: 12.9060, lng: 77.5830, zone: "South Bangalore" },
  { name: "Jayanagar PS",        lat: 12.9260, lng: 77.5830, zone: "South Bangalore" },
  { name: "Electronic City PS",  lat: 12.8440, lng: 77.6600, zone: "South Bangalore" },
  { name: "HSR Layout PS",       lat: 12.9121, lng: 77.6446, zone: "South Bangalore" },
  { name: "Banashankari PS",     lat: 12.9270, lng: 77.5640, zone: "South Bangalore" },
];
policeData.forEach(p => {
  p.location = { type: "Point", coordinates: [p.lng, p.lat] };
  p.active = true;
});
try {
  db.PoliceStations.insertMany(policeData, { ordered: false });
  print(`  → Seeded ${policeData.length} police stations`);
} catch (e) { print(`  ⚠ PoliceStations seed (may already exist): ${e.message}`); }

// ============================================================================
// 15. Hospitals
// ============================================================================
// Reference POI: hardcoded in saferoute_routing_engine_v8.py
// ============================================================================
createCollection("Hospitals", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "lat", "lng"],
      properties: {
        name:    { bsonType: "string" },
        lat:     { bsonType: "double" },
        lng:     { bsonType: "double" },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
        nearest_node_id: { bsonType: ["int", "null"] },
        zone:    { bsonType: ["string", "null"] },
        active:  { bsonType: ["bool", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.Hospitals.createIndex({ location: "2dsphere" });
db.Hospitals.createIndex({ name: 1 }, { unique: true });
print("  → Indexes on Hospitals created");

const hospitalData = [
  { name: "Manipal Hospital",     lat: 12.9592, lng: 77.6474 },
  { name: "Fortis Bannerghatta", lat: 12.8929, lng: 77.5971 },
  { name: "Apollo Jayanagar",    lat: 12.9257, lng: 77.5832 },
  { name: "Narayana Hrudayalaya",lat: 12.8414, lng: 77.6601 },
  { name: "St Johns Hospital",   lat: 12.9452, lng: 77.6153 },
  { name: "Victoria Hospital",   lat: 12.9640, lng: 77.5730 },
  { name: "Bowring Hospital",    lat: 12.9787, lng: 77.6133 },
  { name: "Sakra World Hospital",lat: 12.9582, lng: 77.7091 },
  { name: "Columbia Asia Hebbal",lat: 13.0360, lng: 77.5978 },
  { name: "Aster CMI Hebbal",    lat: 13.0430, lng: 77.5890 },
  { name: "Sparsh Hospital",     lat: 13.0220, lng: 77.5960 },
  { name: "NIMHANS",             lat: 12.9442, lng: 77.5955 },
  { name: "KIMS Hospital",       lat: 12.9330, lng: 77.5790 },
  { name: "Bangalore Baptist",   lat: 13.0254, lng: 77.5963 },
  { name: "Msrit Medical Centre",lat: 13.0213, lng: 77.5637 },
];
hospitalData.forEach(h => {
  h.location = { type: "Point", coordinates: [h.lng, h.lat] };
  h.active = true;
});
try {
  db.Hospitals.insertMany(hospitalData, { ordered: false });
  print(`  → Seeded ${hospitalData.length} hospitals`);
} catch (e) { print(`  ⚠ Hospitals seed (may already exist): ${e.message}`); }

// ============================================================================
// 16. SafeHavens
// ============================================================================
// Snapped graph nodes for safe-haven routing (Phase 19, routing_engine_v8.py).
// Populated at engine startup; stored for API queries.
// ============================================================================
createCollection("SafeHavens", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["haven_type", "node_id"],
      properties: {
        haven_type: {
          bsonType: "string",
          enum: ["police_station", "hospital", "metro_station",
                 "bus_station", "public_area", "cctv_dense_zone"]
        },
        node_id:    { bsonType: ["int", "long"] },
        poi_name:   { bsonType: ["string", "null"] },
        lat:        { bsonType: ["double", "null"] },
        lng:        { bsonType: ["double", "null"] },
        location: {
          bsonType: ["object", "null"],
          properties: {
            type:        { bsonType: "string", enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2,
                           items: { bsonType: "double" } }
          }
        },
        snap_distance_m: { bsonType: ["double", "null"],
                           description: "Distance from original POI to graph node" },
        created_at: { bsonType: ["date", "null"] },
      }
    }
  },
  validationAction: "warn"
});

db.SafeHavens.createIndex({ haven_type: 1, node_id: 1 }, { unique: true });
db.SafeHavens.createIndex({ location: "2dsphere" });
print("  → Indexes on SafeHavens created");

// ============================================================================
// SUMMARY
// ============================================================================
print("\n");
print("═══════════════════════════════════════════════════════════════");
print("  SafeRoute-AI  |  MongoDB Schema Setup Complete");
print("  Database : SAFEROUTE_AI");
print("───────────────────────────────────────────────────────────────");
const colls = db.getCollectionNames();
colls.forEach(c => {
  const cnt = db[c].countDocuments();
  print(`  ${c.padEnd(30)} ${cnt} document(s)`);
});
print("═══════════════════════════════════════════════════════════════");
