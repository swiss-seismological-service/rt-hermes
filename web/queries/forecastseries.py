# for one forecastseries and modelconfig, count events per
# modelrun and realization inside a bounding box
EVENT_COUNT_SERIES = """
    SELECT f.oid AS forecast_oid,
           res.realization_id,
           COUNT(*) AS event_count
    FROM forecast f
    JOIN modelrun mr
        ON f.oid = mr.forecast_oid
        AND mr.modelconfig_oid = :modelconfig_oid
    JOIN modelresult res
        ON mr.oid = res.modelrun_oid
    JOIN eventforecast s
        ON res.oid = s.modelresult_oid
        AND ST_Within(
            s.coordinates,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
    WHERE f.forecastseries_oid = :forecastseries_oid
        AND f.status = 'COMPLETED'
    GROUP BY f.oid, res.realization_id;
"""
