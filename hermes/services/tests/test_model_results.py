"""Contract-based functional tests for model result services."""
from datetime import datetime

import pytest
from sqlalchemy import text

from hermes.datamodel.result_tables import (GridCellTable,
                                            ModelResultTable, TimeStepTable)
from hermes.services.result_service import (save_forecast_catalog,
                                            save_forecast_grrategrid)
from hermes.tests.data_factories import TestDataGenerator


class TestSaveForecastCatalog:
    """Test forecast catalog service contract and business logic."""

    def test_saves_all_catalog_events(
            self, session, modelrun_with_dependencies):
        """Test service persists complete catalog data correctly."""
        forecastseries, modelrun = modelrun_with_dependencies

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

    def test_handles_empty_catalog(self, session, modelrun_with_dependencies):
        """Test service handles empty catalog gracefully."""
        forecastseries, modelrun = modelrun_with_dependencies

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

    def test_spatial_grouping_behavior(
            self, session, modelrun_with_dependencies):
        """Test service correctly groups rate grid by spatial cells."""
        forecastseries, modelrun = modelrun_with_dependencies

        # Create rate grid with 2 spatial cells, multiple entries per cell
        rategrid = TestDataGenerator.create_rate_grid(
            n_cells=2,
            entries_per_cell=2,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        )

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

    def test_single_spatial_cell(self, session, modelrun_with_dependencies):
        """Test service handles single spatial cell correctly."""
        forecastseries, modelrun = modelrun_with_dependencies

        # Create rate grid with single spatial location, multiple entries
        rategrid = TestDataGenerator.create_rate_grid(
            n_cells=1,
            entries_per_cell=3,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        )

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

    def test_error_handling_invalid_grid_id(
            self, session, modelrun_with_dependencies):
        """Test service handles invalid grid_id gracefully."""
        forecastseries, modelrun = modelrun_with_dependencies

        # Create rate grid with invalid grid_id (manually set to test error
        # handling)
        rategrid = TestDataGenerator.create_rate_grid(
            n_cells=1,
            entries_per_cell=2,
            starttime=datetime(2022, 1, 1),
            endtime=datetime(2022, 1, 31)
        )
        # Manually corrupt grid_id to test error handling
        rategrid['grid_id'] = [0, 2]  # Invalid: should be [0, 1] for 2 entries

        # Should raise ValueError for invalid grid_id
        with pytest.raises(ValueError,
                           match="number of modelresult_oids is less"):
            save_forecast_grrategrid(
                session, forecastseries.oid, modelrun.oid, rategrid
            )


class TestServiceDataIntegrity:
    """Test service maintains data integrity across operations."""

    def test_reuse_existing_timestep_and_gridcell(
            self, session, modelrun_with_dependencies):
        """Test service reuses existing TimeStep and GridCell records."""
        forecastseries, modelrun1 = modelrun_with_dependencies

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
