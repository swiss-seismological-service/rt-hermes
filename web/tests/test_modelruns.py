import pytest


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
