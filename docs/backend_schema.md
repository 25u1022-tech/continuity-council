<!-- 04_backend_schema_clickhouse.md -->
# Backend Schema for ClickHouse

## Database

```sql
CREATE DATABASE IF NOT EXISTS continuity_council;
```

---

## Table 1: productions

Stores production metadata.

```sql
CREATE TABLE IF NOT EXISTS continuity_council.productions
(
    production_id String,
    title String,
    start_date Date,
    total_shoot_days UInt8,
    currency String DEFAULT 'USD',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY production_id;
```

---

## Table 2: locations

Stores locations used in the production.

```sql
CREATE TABLE IF NOT EXISTS continuity_council.locations
(
    production_id String,
    location_id String,
    name String,
    location_type String,
    capacity UInt16,
    notes String DEFAULT '',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, location_id);
```

Example `location_type` values:

- `interior`
- `exterior`
- `stage`
- `backlot`

---

## Table 3: cast_members

Stores cast members.

```sql
CREATE TABLE IF NOT EXISTS continuity_council.cast_members
(
    production_id String,
    cast_id String,
    name String,
    role_type String,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (production_id, cast_id);
```

Example `role_type` values:

- `lead`
- `supporting`
- `background`

---

## Table 4: production_schedule

Stores the current shooting schedule.

```sql
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
```

Example `scene_type` values:

- `interior`
- `exterior`
- `stunt`
- `dialogue`
- `cover`

Example `status` values:

- `scheduled`
- `moved`
- `cancelled`
- `completed`

---

## Table 5: location_availability

Stores location availability by shoot day.

```sql
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
```

`available` values:

- `1` = available
- `0` = unavailable

---

## Table 6: cast_availability

Stores cast availability by shoot day.

```sql
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
```

---

## Table 7: disruption_history

This is the main historical analytics table used by the Budget Sentinel Agent.

```sql
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
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (disruption_type, resolution_strategy, created_at);
```

Example `disruption_type` values:

- `lead_actor_unavailable`
- `supporting_actor_unavailable`
- `location_unavailable`
- `weather_delay`
- `equipment_failure`
- `permit_issue`

Example `resolution_strategy` values:

- `shoot_cover_scenes`
- `swap_locations`
- `wait_for_actor`
- `recast_scene`
- `move_to_later_day`
- `split_scene`
- `use_stand_in`

---

## Table 8: disruption_cases

Stores live disruption cases created during the app session.

```sql
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
```

Example `status` values:

- `open`
- `investigating`
- `options_ready`
- `approved`
- `closed`

---

## Table 9: decision_ledger

Stores approved decisions.

```sql
CREATE TABLE IF NOT EXISTS continuity_council.decision_ledger
(
    decision_id String,
    case_id String,
    production_id String,
    disruption_type String,
    selected_option String,
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
```

---

## Table 10: schedule_changes

Stores schedule changes caused by approved decisions.

```sql
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
```

Example `change_type` values:

- `move_scene_day`
- `move_scene_location`
- `swap_scene`
- `cancel_scene`

---

## Sample Analytical Queries

### Query 1: Historical recovery strategy performance

```sql
SELECT
    resolution_strategy,
    AVG(cost_overrun_usd) AS avg_cost_overrun,
    AVG(schedule_delay_hours) AS avg_delay_hours,
    AVG(continuity_risk_score) AS avg_continuity_risk,
    AVG(compliance_risk_score) AS avg_compliance_risk,
    AVG(success_score) AS avg_success_score,
    COUNT(*) AS past_cases
FROM continuity_council.disruption_history
WHERE disruption_type = 'lead_actor_unavailable'
GROUP BY resolution_strategy
ORDER BY avg_cost_overrun ASC;
```

---

### Query 2: Recent historical evidence

```sql
SELECT
    resolution_strategy,
    AVG(cost_overrun_usd) AS avg_cost_overrun,
    AVG(schedule_delay_hours) AS avg_delay_hours,
    COUNT(*) AS past_cases
FROM continuity_council.disruption_history
WHERE disruption_type = 'lead_actor_unavailable'
  AND created_at >= now() - INTERVAL 365 DAY
GROUP BY resolution_strategy
ORDER BY avg_cost_overrun ASC;
```

---

### Query 3: Strategy performance by severity

```sql
SELECT
    severity,
    resolution_strategy,
    AVG(cost_overrun_usd) AS avg_cost_overrun,
    AVG(schedule_delay_hours) AS avg_delay_hours,
    COUNT(*) AS past_cases
FROM continuity_council.disruption_history
WHERE disruption_type = 'lead_actor_unavailable'
GROUP BY severity, resolution_strategy
ORDER BY severity, avg_cost_overrun ASC;
```

---

### Query 4: Audit trail for a production

```sql
SELECT
    decision_id,
    case_id,
    disruption_type,
    selected_option,
    estimated_cost_usd,
    estimated_delay_hours,
    approved_by,
    approved_at
FROM continuity_council.decision_ledger
WHERE production_id = 'prod_001'
ORDER BY approved_at DESC;
```

---

## Sample Insert: disruption_history

```sql
INSERT INTO continuity_council.disruption_history
VALUES
(
    'dis_0001',
    'feature_film',
    'lead_actor_unavailable',
    'high',
    'lead_actor',
    4,
    'shoot_cover_scenes',
    18400,
    3.8,
    0.35,
    0.10,
    0.84,
    'Cover scenes reduced delay and preserved most of Day 2.',
    now()
);
```

---

## Sample Insert: production_schedule

```sql
INSERT INTO continuity_council.production_schedule
VALUES
(
    'prod_001',
    'sc_014',
    'Lead confrontation scene',
    2,
    14,
    'stage_a',
    ['lead_actor', 'supporting_1'],
    'interior',
    0,
    1,
    ['costume_change', 'emotional_continuity'],
    ['sc_013'],
    'scheduled',
    now()
);
```

---

## Data Seeding Strategy

Use a Python script to generate synthetic historical data.

Recommended record count:

- 5,000 to 20,000 rows in `disruption_history`

Recommended distributions:

- 40% `shoot_cover_scenes`
- 25% `swap_locations`
- 15% `move_to_later_day`
- 10% `wait_for_actor`
- 10% other strategies

Recommended cost ranges:

- `shoot_cover_scenes`: $8,000 to $30,000
- `swap_locations`: $15,000 to $45,000
- `move_to_later_day`: $20,000 to $55,000
- `wait_for_actor`: $35,000 to $95,000

Recommended delay ranges:

- `shoot_cover_scenes`: 2 to 6 hours
- `swap_locations`: 3 to 8 hours
- `move_to_later_day`: 5 to 10 hours
- `wait_for_actor`: 8 to 16 hours

---

## Important ClickHouse Design Notes

ClickHouse is optimized for analytical queries, not transactional updates.

For the MVP:

- Treat ClickHouse as append-only where possible
- Use `disruption_cases` and `decision_ledger` as event records
- Do not rely on frequent UPDATE operations
- If schedule state changes are needed, insert schedule change events instead of mutating rows

This is acceptable for a hackathon MVP and aligns with ClickHouse strengths.