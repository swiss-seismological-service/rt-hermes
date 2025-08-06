"""Contract-based functional tests for model result services."""
from datetime import datetime

from sqlalchemy import text

from hermes.datamodel.result_tables import (GridCellTable,
                                            ModelResultTable, TimeStepTable)
from hermes.services.result_service import (save_forecast_catalog,
                                            save_forecast_grrategrid)
from hermes.tests.helpers import TestDataFactory, TestDataGenerator


def create_test_dependencies(session):
    """Create minimal test dependencies for service tests."""
    from hermes.repositories.project import (ForecastRepository,
                                             ForecastSeriesRepository,
                                             ModelConfigRepository,
                                             ProjectRepository)

    # Create test project
    project = TestDataFactory.create_project()
    project = ProjectRepository.create(session, project)

    # Create test forecastseries
    forecastseries = TestDataFactory.create_forecastseries(
        project_oid=project.oid
    )
    forecastseries = ForecastSeriesRepository.create(session, forecastseries)

    # Create test model config
    model_config = TestDataFactory.create_model_config()
    model_config = ModelConfigRepository.create(session, model_config)

    # Create test forecast
    from hermes.schemas import Forecast
    from hermes.schemas.base import EStatus

    forecast = Forecast(
        forecastseries_oid=forecastseries.oid,
        status=EStatus.PENDING,
        starttime=datetime(2022, 1, 1),
        endtime=datetime(2022, 1, 31)
    )
    forecast = ForecastRepository.create(session, forecast)

    # Create test modelrun
    from hermes.datamodel.result_tables import ModelRunTable
    modelrun = ModelRunTable(
        modelconfig_oid=model_config.oid,
        forecast_oid=forecast.oid,
        status=EStatus.PENDING.value
    )
    session.add(modelrun)
    session.commit()

    return forecastseries, modelrun


class TestSaveForecastCatalog:
    """Test forecast catalog service contract and business logic."""

    def test_saves_all_catalog_events(self, session):
        """Test service persists complete catalog data correctly."""
        forecastseries, modelrun = create_test_dependencies(session)

        # Create test catalog with known dimensions
        catalog = TestDataGenerator.create_forecast_catalog(
            n_catalogs=3,
            n_events_per_catalog=10,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        )

        # Execute service
        save_forecast_catalog(
            session, forecastseries.oid, modelrun.oid, catalog
        )

        # Verify business outcomes through database state

        # 1. TimeStep should be created with correct temporal bounds
        timestep = session.query(TimeStepTable).filter_by(
            forecastseries_oid=forecastseries.oid,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        ).first()
        assert timestep is not None, "TimeStep should be created"

        # 2. GridCell should be created with correct spatial bounds
        gridcell = session.query(GridCellTable).filter_by(
            forecastseries_oid=forecastseries.oid,
            depth_min=0,
            depth_max=10
        ).first()
        assert gridcell is not None, "GridCell should be created"

        # 3. ModelResult records should match catalog count
        model_results = session.query(ModelResultTable).filter_by(
            modelrun_oid=modelrun.oid
        ).all()
        assert len(model_results) == 3, "Should create 3 ModelResult records"

        # 4. All ModelResults should link to correct entities
        for result in model_results:
            assert result.timestep_oid == timestep.oid
            assert result.gridcell_oid == gridcell.oid
            assert result.result_type == 'CATALOG'

        # 5. EventForecast records should match total events
        event_count = session.execute(
            text('SELECT COUNT(*) FROM eventforecast WHERE '
                 'modelresult_oid IN (SELECT oid FROM modelresult WHERE '
                 'modelrun_oid = :modelrun_oid)'),
            {'modelrun_oid': modelrun.oid}
        ).scalar()
        assert event_count == 30, "Should create 30 EventForecast records"

    def test_handles_empty_catalog(self, session):
        """Test service handles empty catalog gracefully."""
        forecastseries, modelrun = create_test_dependencies(session)

        # Create empty catalog
        catalog = TestDataGenerator.create_forecast_catalog(
            n_catalogs=1,
            n_events_per_catalog=0
        )

        # Execute service
        save_forecast_catalog(
            session, forecastseries.oid, modelrun.oid, catalog
        )

        # Should still create structural records
        timestep = session.query(TimeStepTable).filter_by(
            forecastseries_oid=forecastseries.oid
        ).first()
        assert timestep is not None

        # But no event records
        event_count = session.execute(
            text('SELECT COUNT(*) FROM eventforecast WHERE '
                 'modelresult_oid IN (SELECT oid FROM modelresult WHERE '
                 'modelrun_oid = :modelrun_oid)'),
            {'modelrun_oid': modelrun.oid}
        ).scalar()
        assert event_count == 0


class TestSaveForecastGRRateGrid:
    """Test GR rate grid service contract and spatial grouping logic."""

    def test_spatial_grouping_behavior(self, session):
        """Test service correctly groups rate grid by spatial cells."""
        forecastseries, modelrun = create_test_dependencies(session)

        # Create rate grid with 2 spatial cells, multiple entries per cell
        import pandas as pd
        rategrid_data = {
            # Cell 1: (5-6, 45-46) - 2 entries, Cell 2: (6-7, 46-47) - 2
            'longitude_min': [5.0, 5.0, 6.0, 6.0],
            'longitude_max': [6.0, 6.0, 7.0, 7.0],
            'latitude_min': [45.0, 45.0, 46.0, 46.0],
            'latitude_max': [46.0, 46.0, 47.0, 47.0],
            'depth_min': [0, 0, 0, 0],
            'depth_max': [10, 10, 10, 10],
            'grid_id': [0, 1, 0, 1],  # 0-indexed within each spatial group
            'b_value': [1.0, 1.1, 1.2, 1.3],
            'a_value': [2.0, 2.1, 2.2, 2.3],
            'magnitude_max': [5.0, 5.1, 5.2, 5.3]
        }

        rategrid = pd.DataFrame(rategrid_data)
        rategrid.starttime = datetime(2022, 1, 1)
        rategrid.endtime = datetime(2022, 1, 31)

        # Execute service
        save_forecast_grrategrid(
            session, forecastseries.oid, modelrun.oid, rategrid
        )

        # Verify spatial grouping outcomes

        # 1. TimeStep created correctly
        timestep = session.query(TimeStepTable).filter_by(
            forecastseries_oid=forecastseries.oid,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        ).first()
        assert timestep is not None

        # 2. Should create 2 unique GridCells (one per spatial group)
        gridcells = session.query(GridCellTable).filter_by(
            forecastseries_oid=forecastseries.oid
        ).all()
        assert len(gridcells) == 2, "Should create 2 spatial GridCells"

        # 3. ModelResults should match total rate grid entries
        model_results = session.query(ModelResultTable).filter_by(
            modelrun_oid=modelrun.oid,
            result_type='GRID'
        ).all()
        assert len(model_results) == 4, "Should create 4 ModelResult records"

        # 4. GRParameters should match ModelResults
        gr_params_count = session.execute(
            text('SELECT COUNT(*) FROM grparameters WHERE '
                 'modelresult_oid IN (SELECT oid FROM modelresult WHERE '
                 'modelrun_oid = :modelrun_oid)'),
            {'modelrun_oid': modelrun.oid}
        ).scalar()
        assert gr_params_count == 4, "Should create 4 GRParameters records"

        # 5. Verify data integrity - each ModelResult links to correct TimeStep
        for result in model_results:
            assert result.timestep_oid == timestep.oid
            assert result.gridcell_oid in [gc.oid for gc in gridcells]

    def test_single_spatial_cell(self, session):
        """Test service handles single spatial cell correctly."""
        forecastseries, modelrun = create_test_dependencies(session)

        # Create rate grid with single spatial location, multiple entries
        import pandas as pd
        rategrid_data = {
            'longitude_min': [5.0, 5.0, 5.0],
            'longitude_max': [6.0, 6.0, 6.0],
            'latitude_min': [45.0, 45.0, 45.0],
            'latitude_max': [46.0, 46.0, 46.0],
            'depth_min': [0, 0, 0],
            'depth_max': [10, 10, 10],
            'grid_id': [0, 1, 2],  # 0-indexed within the single spatial group
            'b_value': [1.0, 1.1, 1.2],
            'a_value': [2.0, 2.1, 2.2],
            'magnitude_max': [5.0, 5.1, 5.2]
        }

        rategrid = pd.DataFrame(rategrid_data)
        rategrid.starttime = datetime(2022, 1, 1)
        rategrid.endtime = datetime(2022, 1, 31)

        # Execute service
        save_forecast_grrategrid(
            session, forecastseries.oid, modelrun.oid, rategrid
        )

        # Should create only 1 GridCell but 3 ModelResults
        gridcells = session.query(GridCellTable).filter_by(
            forecastseries_oid=forecastseries.oid
        ).all()
        assert len(gridcells) == 1, "Should create 1 GridCell"

        model_results = session.query(ModelResultTable).filter_by(
            modelrun_oid=modelrun.oid
        ).all()
        assert len(model_results) == 3, "Should create 3 ModelResult records"

    def test_error_handling_invalid_grid_id(self, session):
        """Test service handles invalid grid_id gracefully."""
        forecastseries, modelrun = create_test_dependencies(session)

        # Create rate grid with invalid grid_id (too high)
        import pandas as pd
        rategrid_data = {
            'longitude_min': [5.0, 5.0],
            'longitude_max': [6.0, 6.0],
            'latitude_min': [45.0, 45.0],
            'latitude_max': [46.0, 46.0],
            'depth_min': [0, 0],
            'depth_max': [10, 10],
            'grid_id': [0, 2],  # Invalid: should be [0, 1] for 2 entries
            'b_value': [1.0, 1.1],
            'a_value': [2.0, 2.1],
            'magnitude_max': [5.0, 5.1]
        }

        rategrid = pd.DataFrame(rategrid_data)
        rategrid.starttime = datetime(2022, 1, 1)
        rategrid.endtime = datetime(2022, 1, 31)

        # Should raise ValueError for invalid grid_id
        import pytest
        with pytest.raises(ValueError,
                           match="number of modelresult_oids is less"):
            save_forecast_grrategrid(
                session, forecastseries.oid, modelrun.oid, rategrid
            )


class TestServiceDataIntegrity:
    """Test service maintains data integrity across operations."""

    def test_reuse_existing_timestep_and_gridcell(self, session):
        """Test service reuses existing TimeStep and GridCell records."""
        forecastseries, modelrun1 = create_test_dependencies(session)

        # Create first catalog
        catalog1 = TestDataGenerator.create_forecast_catalog(
            n_catalogs=2, n_events_per_catalog=5
        )
        save_forecast_catalog(
            session, forecastseries.oid, modelrun1.oid, catalog1
        )

        # Create second modelrun for same forecast
        from hermes.datamodel.result_tables import ModelRunTable
        from hermes.schemas.base import EStatus
        modelrun2 = ModelRunTable(
            modelconfig_oid=modelrun1.modelconfig_oid,
            forecast_oid=modelrun1.forecast_oid,
            status=EStatus.PENDING.value
        )
        session.add(modelrun2)
        session.commit()

        # Create second catalog with same temporal/spatial bounds
        catalog2 = TestDataGenerator.create_forecast_catalog(
            n_catalogs=3, n_events_per_catalog=8
        )
        save_forecast_catalog(
            session, forecastseries.oid, modelrun2.oid, catalog2
        )

        # Should only have 1 TimeStep and 1 GridCell (reused)
        timesteps = session.query(TimeStepTable).filter_by(
            forecastseries_oid=forecastseries.oid
        ).all()
        assert len(timesteps) == 1, "Should reuse existing TimeStep"

        gridcells = session.query(GridCellTable).filter_by(
            forecastseries_oid=forecastseries.oid
        ).all()
        assert len(gridcells) == 1, "Should reuse existing GridCell"

        # Should have ModelResults for both modelruns
        results1 = session.query(ModelResultTable).filter_by(
            modelrun_oid=modelrun1.oid
        ).count()
        results2 = session.query(ModelResultTable).filter_by(
            modelrun_oid=modelrun2.oid
        ).count()
        assert results1 == 2 and results2 == 3
