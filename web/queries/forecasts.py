OBSERVED_EVENTS = """
SELECT eventobservation.*
FROM eventobservation
JOIN seismicityobservation
    ON eventobservation.seismicityobservation_oid = seismicityobservation.oid
WHERE seismicityobservation.forecast_oid = :forecast_id
AND eventobservation.time_value >= :start_time
AND eventobservation.time_value <= :end_time
AND eventobservation.magnitude_value >= :min_mag
AND ST_Within(
    eventobservation.coordinates,
    ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
);
"""

EVENT_COUNT_FORECAST = """
    SELECT res.realization_id,
           COUNT(*) AS event_count
    FROM eventforecast ef
    JOIN modelresult res ON ef.modelresult_oid = res.oid
    JOIN modelrun mr ON ef.modelrun_oid = mr.oid
    WHERE mr.forecast_oid = :forecast_oid
      AND mr.modelconfig_oid = :modelconfig_oid
      AND ST_Within(
          ef.coordinates,
          ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
    GROUP BY res.realization_id
    ORDER BY res.realization_id;
"""
