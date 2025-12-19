import pytest


@pytest.mark.asyncio(loop_scope="module")
class TestModelRunEndpoints:
    async def test_get_modelrun_results(self, test_client, web_scenario):
        """Test that modelrun results endpoint returns 200."""
        response = await test_client.get(
            f"/v1/modelruns/{web_scenario.modelrun.oid}/results")
        assert response.status_code == 200

    async def test_get_modelrun_by_id(self, test_client, web_scenario):
        """Test that modelrun detail endpoint returns correct data."""
        response = await test_client.get(
            f"/v1/modelruns/{web_scenario.modelrun.oid}")
        assert response.status_code == 200
        data = response.json()
        assert data["oid"] == str(web_scenario.modelrun.oid)
