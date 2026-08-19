-- Continuity Council — Sample Analytical Queries (ClickHouse)

-- Query 1: Historical recovery strategy performance (Budget Sentinel core query)
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

-- Query 2: Recent historical evidence (last 365 days)
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

-- Query 3: Strategy performance by severity
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

-- Query 4: Audit trail for a production
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
