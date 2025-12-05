import numpy as np
import pandas as pd
from seismostats import Catalog, ForecastCatalog, ForecastGRRateGrid
from shapely import Point

from hermes.repositories.types import db_to_shapely, shapely_to_db
from hermes.schemas import EventForecast, GRParameters
from hermes.schemas.base import Model

CATALOG_QUANTITY_FIELDS = ['latitude',
                           'longitude', 'depth', 'magnitude', 'time']
RATEGRID_QUANTITY_FIELDS = ['number_events', 'b', 'a', 'alpha', 'mc']


def serialize_seismostats_grrategrid(
        rategrid: ForecastGRRateGrid,
        model: type[Model] = GRParameters) -> list[dict]:
    """
    Serialize a Seismostats ForecastGRRateGrid object to a list of dicts.

    Args:
        rategrid: ForecastGRRateGrid object.
        model: Model object to serialize the rategrid to.

    Returns:
        List of dictionaries, each dictionary representing a rategrid.
    """

    column_renames = {col: f'{col}_value' for col in RATEGRID_QUANTITY_FIELDS}

    rategrid = rategrid.rename(columns=column_renames)

    rategrid = rategrid[[c for c in rategrid.columns if c in list(
        model.model_fields)]]

    return rategrid.to_dict(orient='records')


def deserialize_seismostats_grrategrid(
        rategrid: pd.DataFrame,
        timestep: bool = True) -> ForecastGRRateGrid:
    """
    Deserialize a pd.DataFrame directly from the DB model to a
    Seismostats ForecastGRRateGrid object.

    Args:
        rategrid: Raw tabular data from the database.
        timestep: Whether the data is for a single timestep.

    Returns:
        ForecastGRRateGrid object.
    """
    if rategrid.empty:
        return ForecastGRRateGrid()

    starttime = None
    endtime = None

    # rename value columns to match 'RealQuantity" fields
    column_renames = {f'{col}_value': col for col in RATEGRID_QUANTITY_FIELDS}
    rategrid = rategrid.rename(columns=column_renames)
    rategrid = rategrid.dropna(axis=1, how='all')

    if timestep:
        starttime = rategrid['starttime'].unique()[0].to_pydatetime()
        endtime = rategrid['endtime'].unique()[0].to_pydatetime()
        rategrid = rategrid.drop(columns=['starttime', 'endtime'])

    return ForecastGRRateGrid(rategrid,
                              starttime=starttime,
                              endtime=endtime)


def deserialize_geom_column(geom_col: pd.Series) -> pd.DataFrame:
    """
    Deserialize the geometry column of a rategrid DataFrame.

    Args:
        rategrid: DataFrame with a geometry column.

    Returns:
        DataFrame with the geometry column deserialized.
    """
    if geom_col.empty:
        return geom_col

    geom_col = geom_col.apply(
        lambda x: db_to_shapely(x) if x is not None else None)
    bounds = geom_col.apply(
        lambda geom: geom.bounds if geom is not None else (None, None,
                                                           None, None))
    bounding_cols = pd.DataFrame(bounds.tolist(), columns=[
        'longitude_min', 'latitude_min', 'longitude_max', 'latitude_max'
    ])
    return bounding_cols


def serialize_seismostats_catalog(
    catalog: Catalog,
        model: type[Model] = EventForecast) -> list[dict]:
    """
    Serialize a Seismostats Catalog object to a list of dictionaries.

    Args:
        catalog: Catalog object with the events.
        model: Model object to serialize the events to.
    Returns:
        List of dictionaries, each dictionary representing an event.
    """

    # rename value columns to match 'RealQuantity" fields
    column_renames = {col: f'{col}_value' for col in CATALOG_QUANTITY_FIELDS}
    catalog = catalog.rename(columns=column_renames)

    if 'longitude_value' in catalog.columns and \
            'latitude_value' in catalog.columns:
        catalog['coordinates'] = catalog.apply(
            lambda row: shapely_to_db(
                Point(row['longitude_value'], row['latitude_value'])),
            axis=1)

    # only keep columns that are in the model
    catalog = catalog[[c for c in catalog.columns if c in list(
        model.model_fields)]]

    # replace NaNs with None for database compatibility
    catalog = catalog.replace({pd.NA: None,
                               np.nan: None})

    events = catalog.to_dict(orient='records')

    return events


def deserialize_seismostats_catalog(
        catalog: pd.DataFrame,
        gridcell: bool = True,
        timestep: bool = True
) -> ForecastCatalog:
    """
    Deserialize a pd.DataFrame directly from the DB model to a
    Seismostats Catalog object.

    Args:
        rategrid: Raw tabular data from the database.
        gridcell: Whether the data is for a single gridcell.
        timestep: Whether the data is for a single timestep.

    Returns:
        Catalog object.
    """
    if catalog.empty:
        return Catalog()

    starttime = None
    endtime = None
    bounding_polygon = None
    depth_min = None
    depth_max = None

    # rename value columns to match 'RealQuantity" fields
    column_renames = {f'{col}_value': col for col in CATALOG_QUANTITY_FIELDS}
    catalog = catalog.rename(columns=column_renames)

    if gridcell:
        bounding_polygon = db_to_shapely(catalog['geom'][0])
        depth_min = catalog['depth_min'][0]
        depth_max = catalog['depth_max'][0]
        catalog = catalog.drop(columns=['depth_min', 'depth_max'])
    else:
        boundingbox = deserialize_geom_column(catalog['geom'])
        catalog = pd.concat([boundingbox, catalog], axis=1)

    if timestep:
        starttime = catalog['starttime'][0]
        endtime = catalog['endtime'][0]
        catalog = catalog.drop(columns=['starttime', 'endtime'])

    # drop oid and modelresult_oid columns
    catalog = catalog.drop(
        columns=['oid', 'modelresult_oid', 'coordinates', 'geom'])
    catalog = catalog.dropna(axis=1, how='all')

    return Catalog(catalog,
                   starttime=starttime,
                   endtime=endtime,
                   bounding_polygon=bounding_polygon,
                   depth_min=depth_min,
                   depth_max=depth_max)
