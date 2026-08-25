-- Continuity Council — ClickHouse Schema
-- Production recovery, schedule optimization, and economic risk intelligence

CREATE DATABASE IF NOT EXISTS continuity_council;

-- Table 1: productions
CREATE TABLE IF NOT EXISTS continuity_council.productions
(
    production_id String,
    title String,
    start_date Date,
    total_shoot_days UInt8,
    currency String DEFAULT 'USD',
    director String DEFAULT '',
    tier String DEFAULT 'mid',
    studio_id String DEFAULT 'global',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY production_id;

-- Table 2: locations
CREATE TABLE IF NOT EXISTS continuity_council.locations
(
    production_id String,
    location_id String,
    name String,
    location_type String,
    capacity UInt16,
    daily_fee_usd Int64 DEFAULT 5000,
    latitude Float64 DEFAULT 0.0,
    longitude Float64 DEFAULT 0.0,
    currency_code String DEFAULT 'USD',
    notes String DEFAULT '',
    country_code String DEFAULT 'US',
    country_mult Float32 DEFAULT 1.0,
    city_tier String DEFAULT 'tier_1',
    geo_mult Float32 DEFAULT 1.0,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, location_id);

-- Table 3: cast_members
CREATE TABLE IF NOT EXISTS continuity_council.cast_members
(
    production_id String,
    cast_id String,
    name String,
    role_type String,
    day_rate_usd Int64 DEFAULT 1100,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, cast_id);

-- Table 4: rate_cards (Industry benchmarks for bottom-up estimation)
CREATE TABLE IF NOT EXISTS continuity_council.rate_cards
(
    tier String,
    item String,
    unit String,
    daily_rate_usd Int64,
    source_note String,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (tier, item);

-- Table 5: production_schedule
CREATE TABLE IF NOT EXISTS continuity_council.production_schedule
(
    production_id String,
    scene_id String,
    scene_title String,
    shoot_day UInt8,
    sequence_order UInt16,
    location_id String,
    required_cast Array(String),
    scene_type String,
    is_cover_scene UInt8 DEFAULT 0,
    priority UInt8 DEFAULT 3,
    continuity_tags Array(String),
    depends_on Array(String),
    status String DEFAULT 'scheduled',
    updated_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, shoot_day, scene_id);

-- Table 6: location_availability
CREATE TABLE IF NOT EXISTS continuity_council.location_availability
(
    production_id String,
    location_id String,
    shoot_day UInt8,
    available UInt8,
    notes String DEFAULT '',
    updated_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, location_id, shoot_day);

-- Table 7: cast_availability
CREATE TABLE IF NOT EXISTS continuity_council.cast_availability
(
    production_id String,
    cast_id String,
    shoot_day UInt8,
    available UInt8,
    reason String DEFAULT '',
    updated_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, cast_id, shoot_day);

-- Table 8: disruption_history (main analytics table for Budget Sentinel)
CREATE TABLE IF NOT EXISTS continuity_council.disruption_history
(
    disruption_id String,
    production_type String,
    disruption_type String,
    severity String,
    affected_role String,
    affected_scene_count UInt16,
    resolution_strategy String,
    cost_overrun_usd Int64,
    schedule_delay_hours Float32,
    continuity_risk_score Float32,
    compliance_risk_score Float32,
    success_score Float32,
    notes String DEFAULT '',
    studio_id String DEFAULT 'global',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (disruption_type, resolution_strategy, created_at);

-- Materialized strategy aggregates used by Budget Sentinel evidence queries.
CREATE MATERIALIZED VIEW IF NOT EXISTS continuity_council.strategy_performance_mv
ENGINE = AggregatingMergeTree()
ORDER BY (disruption_type, strategy, severity)
POPULATE
AS SELECT
    disruption_type,
    resolution_strategy AS strategy,
    severity,
    avgState(cost_overrun_usd) AS avg_cost,
    avgState(schedule_delay_hours) AS avg_delay,
    countState() AS sample_size,
    avgState(continuity_risk_score) AS avg_continuity_risk,
    avgState(compliance_risk_score) AS avg_compliance_risk,
    avgState(success_score) AS avg_success_score
FROM continuity_council.disruption_history
GROUP BY disruption_type, resolution_strategy, severity;

-- Table 9: disruption_cases
CREATE TABLE IF NOT EXISTS continuity_council.disruption_cases
(
    case_id String,
    production_id String,
    disruption_type String,
    severity String,
    affected_day UInt8,
    affected_cast_id String DEFAULT '',
    affected_location_id String DEFAULT '',
    details String DEFAULT '',
    status String DEFAULT 'open',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, created_at);

-- Table 10: decision_ledger
CREATE TABLE IF NOT EXISTS continuity_council.decision_ledger
(
    decision_id String,
    case_id String,
    production_id String,
    disruption_type String,
    selected_option String,
    affected_location_id String DEFAULT '',
    option_summary String,
    estimated_cost_usd Int64,
    estimated_delay_hours Float32,
    continuity_risk_score Float32,
    compliance_risk_score Float32,
    evidence_json String,
    approved_by String,
    approved_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, approved_at);

-- Table 11: schedule_changes
CREATE TABLE IF NOT EXISTS continuity_council.schedule_changes
(
    change_id String,
    decision_id String,
    production_id String,
    scene_id String,
    old_shoot_day UInt8,
    new_shoot_day UInt8,
    old_location_id String,
    new_location_id String,
    change_type String,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, created_at);
