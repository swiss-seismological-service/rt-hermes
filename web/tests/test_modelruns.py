import pytest

from web.repositories.results import AsyncEventForecastRepository


@pytest.mark.asyncio
class TestModelRunEndpoints:
    async def test_get_modelrun_results(self, test_client, scenario_web):
        """Test that modelrun results endpoint returns 200."""
        response = await test_client.get(
            f"/v1/modelruns/{scenario_web.modelrun.oid}/results")
        assert response.status_code == 200

    async def test_get_modelrun_by_id(self, test_client, scenario_web):
        """Test that modelrun detail endpoint returns correct data."""
        response = await test_client.get(
            f"/v1/modelruns/{scenario_web.modelrun.oid}")
        assert response.status_code == 200
        data = response.json()
        assert data["oid"] == str(scenario_web.modelrun.oid)


@pytest.mark.asyncio
class TestEventForecastRepository:
    """Tests for AsyncEventForecastRepository methods."""

    async def test_get_forecast_catalog_returns_events(
            self, async_session, scenario_with_events):
        """Test get_forecast_catalog returns correct event data."""
        result = await AsyncEventForecastRepository.get_forecast_catalog(
            async_session, scenario_with_events.modelrun.oid)

        assert len(result) == scenario_with_events.event_count

    async def test_get_forecast_catalog_empty_modelrun(
            self, async_session, scenario_web):
        """
        Test get_forecast_catalog returns empty
        for modelrun without events.
        """
        result = await AsyncEventForecastRepository.get_forecast_catalog(
            async_session, scenario_web.modelrun.oid)

        assert len(result) == 0


@pytest.mark.asyncio
class TestEventCountsEndpoint:
    """Tests for the eventcounts endpoint using EVENTCOUNTS SQL query."""

    async def test_eventcounts_returns_grid_data(
            self, test_client, scenario_with_events):
        """Test eventcounts endpoint returns event count grid."""
        response = await test_client.get(
            f"/v1/modelruns/{scenario_with_events.modelrun.oid}/eventcounts",
            params={
                "min_lon": 5.0,
                "min_lat": 45.0,
                "max_lon": 11.0,
                "max_lat": 48.0,
                "res_lon": 0.5,
                "res_lat": 0.5
            }
        )
        assert response.status_code == 200
        content = response.text
        assert "grid_lon" in content
        assert "grid_lat" in content
        assert "event_count" in content
        assert "7.25,46.25,64" in content

    async def test_eventcounts_empty_modelrun(
            self, test_client, scenario_web):
        """Test eventcounts endpoint with modelrun that has no events."""
        response = await test_client.get(
            f"/v1/modelruns/{scenario_web.modelrun.oid}/eventcounts",
            params={
                "min_lon": 5.0,
                "min_lat": 45.0,
                "max_lon": 11.0,
                "max_lat": 48.0,
                "res_lon": 0.5,
                "res_lat": 0.5
            }
        )

        assert response.status_code == 200
