EVENTCOUNTS = """
WITH grid_cells AS (
    SELECT ST_SnapToGrid(eventforecast.coordinates,
                        :min_lon,
                        :min_lat,
                        :res_lon,
                        :res_lat
                        ) AS grid_geom,
        COUNT(*) AS event_count
    FROM eventforecast
    WHERE eventforecast.modelrun_oid = :modelrun_oid
        AND ST_Within(
            eventforecast.coordinates,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
    GROUP BY grid_geom
)
SELECT
    ST_X(grid_geom) AS grid_lon,
    ST_Y(grid_geom) AS grid_lat,
    event_count
FROM grid_cells;
"""
