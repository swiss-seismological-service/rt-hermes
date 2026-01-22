# for one forecastseries and modelconfig, count events per
# forecast inside a bounding box
EVENT_COUNT_SERIES = """
    SELECT f.oid AS forecast_oid,
           COUNT(*) AS event_count
    FROM forecast f
    JOIN modelrun mr
        ON f.oid = mr.forecast_oid
        AND mr.modelconfig_oid = :modelconfig_oid
    JOIN eventforecast s
        ON s.modelrun_oid = mr.oid
        AND ST_Within(
            s.coordinates,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
    WHERE f.forecastseries_oid = :forecastseries_oid
        AND f.status = 'COMPLETED'
    GROUP BY f.oid;
"""
