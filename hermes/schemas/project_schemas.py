import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from shapely import Polygon
from typing_extensions import Self

from hermes.repositories.types import PolygonType, db_to_shapely
from hermes.schemas.base import CreationInfoMixin, EInput, EStatus, Model
from hermes.utils.geometry import convert_input_to_polygon


class Project(CreationInfoMixin):
    oid: UUID | None = None
    name: str | None = None
    starttime: datetime | None = None
    endtime: datetime | None = None

    description: str | None = None


class ForecastSeriesSchedule(Model):
    schedule_starttime: datetime | None = None
    schedule_interval: int | None = None
    schedule_endtime: datetime | None = None
    schedule_id: UUID | None = None
    schedule_active: bool | None = None
    forecast_starttime: datetime | None = None
    forecast_endtime: datetime | None = None
    forecast_duration: int | None = None


class ForecastSeriesConfig(CreationInfoMixin):
    oid: UUID | None = None
    project_oid: UUID | None = None
    name: str | None = None
    description: str | None = None
    status: EStatus | None = None

    observation_starttime: datetime | None = None
    observation_endtime: datetime | None = None
    observation_window: int | None = None

    bounding_polygon: Polygon | None = None
    depth_min: float | None = None
    depth_max: float | None = None

    injection_plans: list[dict] | None = Field(None, exclude=True)

    model_settings: dict = {}

    tags: list[str] = []

    seismicityobservation_required: EInput = EInput.REQUIRED
    injectionobservation_required: EInput = EInput.REQUIRED
    injectionplan_required: EInput = EInput.REQUIRED

    fdsnws_url: str | None = None
    hydws_url: str | None = None

    @model_validator(mode='after')
    def validate_observation_window(self):
        if self.observation_starttime and self.observation_window:
            raise ValueError("You can't set both observation_starttime "
                             "and observation_window.")
        return self

    @field_validator('bounding_polygon', mode='before')
    @classmethod
    def validate_bounding_polygon(cls, value: Any) -> Self:
        if isinstance(value, dict):
            value = json.dumps(value)

        if isinstance(value, PolygonType):
            return db_to_shapely(value)

        if isinstance(value, str):
            return convert_input_to_polygon(value)

        return value


class ForecastSeries(ForecastSeriesConfig, ForecastSeriesSchedule):
    pass


class Forecast(CreationInfoMixin):
    oid: UUID | None = None

    status: EStatus | None = None

    starttime: datetime | None = None
    endtime: datetime | None = None

    forecastseries_oid: UUID | None = None

    seismicity_observation: str | None = Field(None, exclude=True)
    injection_observation: list[dict] | None = Field(None, exclude=True)


class Tag(Model):
    oid: UUID | None = None
    name: str | None = None
