import io
from datetime import datetime
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, HTTPException, Response
from seismostats import Catalog
from sqlalchemy import text

from hermes.schemas.base import EResultType
from hermes.schemas.result_schemas import ModelRun
from web.queries.forecasts import EVENT_COUNT_FORECAST, OBSERVED_EVENTS
from web.repositories.data import AsyncInjectionObservationRepository
from web.repositories.database import DBSessionDep, pandas_read_sql_async
from web.repositories.project import (AsyncForecastRepository,
                                      AsyncModelConfigRepository)
from web.repositories.results import AsyncModelRunRepository
from web.schemas import ForecastJSON

router = APIRouter(prefix="/forecasts", tags=['forecast'])


@router.get("/{forecast_oid}",
            response_model=ForecastJSON,
            response_model_exclude_none=True)
async def get_forecast(db: DBSessionDep,
                       forecast_oid: UUID):
    """
    Returns a single Forecast
    """

    db_result = await AsyncForecastRepository.get_by_id_joined(
        db, forecast_oid)

    if not db_result:
        raise HTTPException(status_code=404, detail="No forecast found.")

    return db_result


@router.get("/{forecast_oid}/injectionobservations",
            response_class=Response)
async def get_injectionobservation_hydjson(
        db: DBSessionDep, forecast_oid: UUID):

    db_result = await AsyncInjectionObservationRepository.get_by_forecast(
        db, forecast_oid)

    if not db_result:
        raise HTTPException(
            status_code=404,
            detail="No Forecast or injectionobservation found.")

    return Response(content=db_result.data,
                    media_type='application/json')


@router.get("/{forecast_id}/seismicityobservation",
            response_class=Response,
            responses={200: {"content": {"application/xml": {}}}})
async def get_seismicityobservation(
        db: DBSessionDep,
        forecast_id: UUID,
        start_time: datetime = datetime.min,
        min_lon: float = -180,
        min_lat: float = -90,
        max_lon: float = 180,
        max_lat: float = 90,
        min_mag: float = -10,
        end_time: datetime = datetime.max):
    """
    Returns the seismicity observation for a given forecast.
    """
    stmt = text(OBSERVED_EVENTS).bindparams(
        forecast_id=forecast_id,
        start_time=start_time,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        min_mag=min_mag,
        end_time=end_time
    )

    cat = await pandas_read_sql_async(stmt, db)
    cat = Catalog(cat.rename(columns=lambda col:
                             col.removesuffix('_value')))
    qml = cat.to_quakeml()
    return Response(content=qml,
                    media_type="application/xml")


@router.get("/{forecast_oid}/modelruns",
            response_model=list[ModelRun])
async def get_modelruns(db: DBSessionDep,
                        forecast_oid: UUID):
    """
    Returns a list of ModelRuns for this forecast.
    """
    db_result = await AsyncModelRunRepository.get_by_forecast(
        db, forecast_oid)

    return db_result


@router.get("/{forecast_oid}/eventcounts")
async def get_forecast_eventcounts(
        db: DBSessionDep,
        forecast_oid: UUID,
        modelconfig_oid: UUID,
        min_lon: float = -180,
        min_lat: float = -90,
        max_lon: float = 180,
        max_lat: float = 90):
    """
    Returns event counts per realization for a forecast and modelconfig.
    """
    config = await AsyncModelConfigRepository.get_by_id(db, modelconfig_oid)
    if config is None:
        raise HTTPException(status_code=404, detail="ModelConfig not found.")
    if config.result_type != EResultType.CATALOG:
        raise HTTPException(
            status_code=400, detail="Wrong result type for this endpoint.")

    stmt = text(EVENT_COUNT_FORECAST).bindparams(
        forecast_oid=forecast_oid,
        modelconfig_oid=modelconfig_oid,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
    )

    result = await db.execute(stmt)
    rows = result.fetchall()
    columns = result.keys()

    df = pd.DataFrame(rows, columns=columns)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    return Response(content=csv_buffer.getvalue(), media_type="text/csv")
