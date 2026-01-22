# for one forecastseries and modelconfig, count events per
# modelrun and realization inside a bounding box
EVENT_COUNT_SERIES = """
    SELECT mr.forecast_oid AS forecast_oid,
           res.realization_id,
           COUNT(*) AS event_count
    FROM eventforecast s
    JOIN modelrun mr ON s.modelrun_oid = mr.oid
    JOIN forecast f ON mr.forecast_oid = f.oid
    JOIN modelresult res ON s.modelresult_oid = res.oid
    WHERE mr.modelconfig_oid = :modelconfig_oid
      AND f.forecastseries_oid = :forecastseries_oid
      AND f.status = 'COMPLETED'
      AND ST_Within(
              s.coordinates,
              ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
    GROUP BY mr.forecast_oid, res.realization_id;
"""
