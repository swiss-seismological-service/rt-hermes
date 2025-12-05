import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import field_validator
from shapely import Point, Polygon

from hermes.repositories.types import PolygonType, db_to_shapely
from hermes.schemas.base import EResultType, EStatus, Model, real_value_mixin
from hermes.utils.geometry import convert_input_to_polygon


class ModelRun(Model):
    oid: UUID | None = None
    status: EStatus | None = None

    modelconfig_oid: UUID | None = None
    forecast_oid: UUID | None = None
    injectionplan_oid: UUID | None = None


class ModelResult(Model):
    oid: UUID | None = None
    result_type: EResultType | None = None
    timestep_oid: UUID | None = None
    gridcell_oid: UUID | None = None
    modelrun_oid: UUID | None = None


class TimeStep(Model):
    oid: UUID | None = None
    starttime: datetime | None = None
    endtime: datetime | None = None
    forecastseries_oid: UUID | None = None

    @field_validator('starttime', 'endtime', mode='after')
    @classmethod
    def validate(cls, value: datetime):
        value = value.replace(microsecond=0)
        return value


class GridCell(Model):
    oid: UUID | None = None
    geom: Polygon | None = None
    depth_min: float | None = None
    depth_max: float | None = None
    forecastseries_oid: UUID | None = None

    @field_validator('geom', mode='before')
    @classmethod
    def validate_geom(cls, value: Any):
        if isinstance(value, dict):
            value = json.dumps(value)

        if isinstance(value, PolygonType):
            return db_to_shapely(value)

        if isinstance(value, str):
            return convert_input_to_polygon(value)

        return value


class EventForecast(real_value_mixin('longitude', float),
                    real_value_mixin('latitude', float),
                    real_value_mixin('depth', float),
                    real_value_mixin('magnitude', float),
                    real_value_mixin('time', datetime)
                    ):
    oid: UUID | None = None
    magnitude_type: str | None = None
    modelresult_oid: UUID | None = None
    coordinates: Point | None = None


class GRParameters(real_value_mixin('number_events', float),
                   real_value_mixin('b', float),
                   real_value_mixin('a', float),
                   real_value_mixin('mc', float),
                   real_value_mixin('alpha', float)
                   ):
    oid: UUID | None = None
    modelresult_oid: UUID | None = None
    modelrun_oid: UUID | None = None
