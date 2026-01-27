from uuid import UUID

from fastapi import APIRouter, HTTPException

from hermes.schemas.model_schemas import ModelConfig
from web.repositories.data import AsyncInjectionPlanRepository
from web.repositories.database import DBSessionDep
from web.repositories.project import (AsyncForecastRepository,
                                      AsyncForecastSeriesRepository,
                                      AsyncModelConfigRepository)
from web.schemas import ForecastJSON, ForecastSeriesJSON, InjectionPlanJSON

router = APIRouter(prefix='/forecastseries', tags=['forecastseries'])


@router.get("/{forecastseries_oid}",
            response_model=ForecastSeriesJSON,
            response_model_exclude_none=True)
async def get_forecastseries(db: DBSessionDep,
                             forecastseries_oid: UUID):
    """
    Returns a ForecastSeries
    """

    db_result = await AsyncForecastSeriesRepository.get_by_id(
        db, forecastseries_oid, joined_attrs=['_tags', 'injectionplans'],
        override_model=ForecastSeriesJSON)

    if not db_result:
        raise HTTPException(
            status_code=404, detail="Forecastseries not found.")

    db_result.modelconfigs = await AsyncModelConfigRepository.get_by_tags(
        db, db_result.tags)

    return db_result


@router.get("/{forecastseries_oid}/forecasts",
            response_model=list[ForecastJSON],
            response_model_exclude_none=True)
async def get_forecasts(db: DBSessionDep,
                        forecastseries_oid: UUID):
    """
    Returns a list of ForecastSeries
    """
    db_result = await AsyncForecastRepository.get_by_forecastseries_joined(
        db, forecastseries_oid)

    return db_result


@router.get("/{forecastseries_oid}/modelconfigs",
            response_model=list[ModelConfig],
            response_model_exclude_none=True)
async def get_modelconfigs(db: DBSessionDep,
                           forecastseries_oid: UUID):
    """
    Returns a list of ModelConfigs
    """

    fs = await AsyncForecastSeriesRepository.get_by_id(
        db, forecastseries_oid)

    if not fs:
        raise HTTPException(status_code=404, detail="No forecastseries found.")

    db_result = await AsyncModelConfigRepository.get_by_tags(
        db, fs.tags)

    return db_result


@router.get("/{forecastseries_oid}/injectionplans",
            response_model=list[InjectionPlanJSON],
            response_model_exclude_none=True)
async def get_injectionplans(db: DBSessionDep,
                             forecastseries_oid: UUID):
    """
    Returns a list of InjectionPlans
    """

    db_result = await AsyncInjectionPlanRepository.get_by_forecastseries(
        db, forecastseries_oid)

    return db_result
