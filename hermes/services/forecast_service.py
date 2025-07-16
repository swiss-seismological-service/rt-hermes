from uuid import UUID

from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastRepository


def delete_forecast(forecast_oid: UUID):
    with DatabaseSession() as session:

        injectionplans = InjectionPlanRepository.get_ids_by_forecast(
            session, forecast_oid)

        ForecastRepository.delete(session, forecast_oid)

        for ip in injectionplans:
            InjectionPlanRepository.delete(session, ip)

    return f"Forecast {forecast_oid} deleted."
