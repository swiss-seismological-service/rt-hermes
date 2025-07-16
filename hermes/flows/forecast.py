import logging
from datetime import datetime, timedelta
from uuid import UUID

from prefect import flow, get_run_logger, runtime

from hermes.io.hydraulics import HydraulicsDataSource
from hermes.io.seismicity import SeismicityDataSource
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastSeriesRepository
from hermes.schemas.model_schemas import ModelConfig
from hermes.schemas.project_schemas import Forecast, ForecastSeries


@flow(name="Run Forecast",
      description="Runs a forecast for a given ForecastSeries.",
      tags=["forecast", "run"])
def run_forecast(forecastseries_oid: UUID,
                 starttime: datetime | None = None,
                 endtime: datetime | None = None) -> None:
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    with DatabaseSession() as session:
        forecastseries: ForecastSeries = \
            ForecastSeriesRepository.get_by_id(session,
                                               forecastseries_oid)
        modelconfigs: list[ModelConfig] = \
            ForecastSeriesRepository.get_model_configs(session,
                                                       forecastseries_oid)

    if not modelconfigs:
        logger.warning('No ModelConfigs associated with the '
                       'ForecastSeries. Exiting.')
        return None

    starttime = forecastseries.forecast_starttime or starttime or \
        runtime.flow_run.scheduled_start_time

    forecast_builder = ForecastBuilder(forecastseries=forecastseries,
                                       modelconfigs=modelconfigs)

    forecast_builder.build(starttime,
                           endtime)


class ForecastBuilder:
    def __init__(self,
                 forecastseries: ForecastSeries,
                 modelconfigs: list[ModelConfig]):

        self.forecastseries: ForecastSeries = forecastseries
        self.modelconfigs: ModelConfig = modelconfigs
        self.forecast: Forecast = None

        self.starttime: datetime
        self.endtime: datetime

        self.catalog_data_source: SeismicityDataSource = None
        self.hydraulic_data_source: HydraulicsDataSource = None

    def build(self,
              starttime: datetime | None = None,
              endtime: datetime | None = None):

        self._calculate_forecast_timebounds(starttime=starttime,
                                            endtime=endtime)

        self.forecast = Forecast(
            forecastseries_oid=self.forecastseries.oid,
            starttime=self.starttime,
            endtime=self.endtime
        )

    def _calculate_forecast_timebounds(self,
                                       starttime: datetime,
                                       endtime: datetime) -> None:
        """
        Sets the forecast start and end times.

        starttime:  When running forecasts manually or catching up on a
                    schedule, the starttime should be passed as an argument.
                    Else, a fixed starttime can be set on the ForecastSeries.
                    If the forecasts are run on a schedule, the starttime
                    will be the scheduled start time of the flow run.
        endtime:    When running forecasts manually or catching up on a
                    schedule, the endtime should be passed as an argument.
                    Else, it is given by the two following fields on
                    the ForecastSeries:
                    forecast_duration, forecast_endtime.
        """

        if self.starttime.tzinfo is not None:
            self.starttime = self.starttime.replace(tzinfo=None)

        if self.forecastseries.forecast_starttime is not None and \
                self.starttime > self.forecastseries.forecast_starttime:
            raise ValueError(
                "Starttime can't be later than forecast_starttime.")

        # set endtime, forecast_duration takes precedence over forecast_endtime
        self.endtime = endtime or \
            (self.starttime
             + timedelta(seconds=self.forecastseries.forecast_duration)
             if self.forecastseries.forecast_duration else None) or \
            self.forecastseries.forecast_endtime
        # endtime can't be later than forecast_endtime
        if self.forecastseries.forecast_endtime is not None and \
                self.forecastseries.forecast_endtime < self.endtime:
            self.endtime = self.forecastseries.forecast_endtime

        if self.endtime.tzinfo is not None:
            self.endtime = self.endtime.replace(tzinfo=None)
