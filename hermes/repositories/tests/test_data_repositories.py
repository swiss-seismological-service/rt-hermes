import json
import os

import pandas as pd
from hydws.parser import BoreholeHydraulics
from seismostats import Catalog
from sqlalchemy import text

from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


class TestSeismicityObservationRepository:
    def test_create_from_catalog_and_quakeml(self, session, connection,
                                             full_scenario):
        """Test both create_from_catalog and create_from_quakeml methods"""
        catalog_path = os.path.join(MODULE_LOCATION, 'catalog.parquet.gzip')
        catalog = Catalog(pd.read_parquet(catalog_path))

        # Test create_from_catalog
        seismicity = SeismicityObservationRepository.create_from_catalog(
            session, catalog, full_scenario.forecast.oid)

        count = connection.execute(
            text('SELECT COUNT(*) FROM seismicityobservation '
                 'WHERE oid = :oid'),
            {'oid': seismicity.oid}
        ).scalar()
        assert count == 1

        obs_db = SeismicityObservationRepository.get_by_id(
            session, seismicity.oid)
        assert obs_db.data.decode('utf-8')

        # Test create_from_quakeml
        catalog_qml = catalog.to_quakeml()
        SeismicityObservationRepository.create_from_quakeml(
            session, catalog_qml, full_scenario.forecast.oid)

        total_count = connection.execute(
            text('SELECT COUNT(*) FROM seismicityobservation')).scalar()
        assert total_count == 2


class TestInjectionObservationRepository:
    def test_create_methods_and_delete(
            self, session, connection, full_scenario):
        """Test create_from_hydjson, create_from_borehole_hydraulics,
        and delete"""
        with open(os.path.join(MODULE_LOCATION, 'hydraulics.json'), 'rb') as f:
            [data] = json.load(f)

        # Test create_from_hydjson
        injection = InjectionObservationRepository.create_from_hydjson(
            session, json.dumps(data), full_scenario.forecast.oid)

        count = connection.execute(
            text('SELECT COUNT(*) FROM injectionobservation '
                 'WHERE oid = :oid'),
            {'oid': injection.oid}
        ).scalar()
        assert count == 1

        # Test create_from_borehole_hydraulics
        borehole_hydraulics = BoreholeHydraulics(data)
        injection2 = InjectionObservationRepository.\
            create_from_borehole_hydraulics(
                session, borehole_hydraulics, full_scenario.forecast.oid)

        count2 = connection.execute(
            text('SELECT COUNT(*) FROM injectionobservation WHERE oid = :oid'),
            {'oid': injection2.oid}
        ).scalar()
        assert count2 == 1

        # Test delete
        InjectionObservationRepository.delete(session, injection.oid)
        count_after_delete = connection.execute(
            text('SELECT COUNT(*) FROM injectionobservation WHERE oid = :oid'),
            {'oid': injection.oid}
        ).scalar()
        assert count_after_delete == 0


class TestInjectionPlanRepository:
    def test_create_methods_delete_and_get_by_forecastseries(
            self, session, connection, full_scenario):
        """Test create_from_hydjson, create_from_borehole_hydraulics,
        delete, and get_by_forecastseries"""
        with open(os.path.join(MODULE_LOCATION, 'hydraulics.json'), 'rb') as f:
            [data] = json.load(f)

        # Test create_from_hydjson
        injectionplan = InjectionPlanRepository.create_from_hydjson(
            session, json.dumps(data), 'test_plan',
            full_scenario.forecastseries.oid)

        count = connection.execute(
            text('SELECT COUNT(*) FROM injectionplan WHERE oid = :oid'),
            {'oid': injectionplan.oid}
        ).scalar()
        assert count == 1

        # Test create_from_borehole_hydraulics
        borehole_hydraulics = BoreholeHydraulics(data)
        injectionplan2 = InjectionPlanRepository.\
            create_from_borehole_hydraulics(
                session, borehole_hydraulics, 'test_plan2',
                full_scenario.forecastseries.oid)

        count2 = connection.execute(
            text('SELECT COUNT(*) FROM injectionplan WHERE oid = :oid'),
            {'oid': injectionplan2.oid}
        ).scalar()
        assert count2 == 1

        # Test get_by_forecastseries
        plans = InjectionPlanRepository.get_by_forecastseries(
            session, full_scenario.forecastseries.oid)
        assert len(plans) == 2

        # Test delete
        InjectionPlanRepository.delete(session, injectionplan.oid)
        count_after_delete = connection.execute(
            text('SELECT COUNT(*) FROM injectionplan WHERE oid = :oid'),
            {'oid': injectionplan.oid}
        ).scalar()
        assert count_after_delete == 0


class TestEventObservationRepository:
    def test_events_created_by_seismicity_operations(
            self, session, connection, full_scenario):
        """Verify that EventObservation records are created when
        SeismicityObservationRepository methods are called"""
        catalog_path = os.path.join(MODULE_LOCATION, 'catalog.parquet.gzip')
        catalog = Catalog(pd.read_parquet(catalog_path))

        # EventObservations are created internally by
        # SeismicityObservationRepository
        SeismicityObservationRepository.create_from_catalog(
            session, catalog, full_scenario.forecast.oid)

        count = connection.execute(
            text('SELECT COUNT(*) FROM eventobservation')
        ).scalar()
        assert count > 0
