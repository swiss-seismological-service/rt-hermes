import os
import pickle

import pandas as pd
from numpy.testing import assert_almost_equal
from seismostats import Catalog

from hermes.io.serialize import (serialize_seismostats_catalog,
                                 serialize_seismostats_grrategrid)
from hermes.io.tests.test_seismicity import MODULE_LOCATION


class TestGRRategrid:
    def test_rategrid_serialization(self):
        rategrid_path = os.path.join(MODULE_LOCATION, 'forecastgrrategrid.pkl')
        with open(rategrid_path, 'rb') as f:
            data = pickle.load(f)

        rategrid = data[-1]

        rategrid = serialize_seismostats_grrategrid(rategrid)
        assert_almost_equal(rategrid[-1]['b_value'], 2.097799, 5)


class TestCatalog:
    def test_catalog_serialization(self):
        qml_path = os.path.join(MODULE_LOCATION, 'quakeml.xml')
        catalog = Catalog.from_quakeml(qml_path,
                                       include_uncertainties=True,
                                       include_quality=True)

        for _ in range(6):
            catalog = pd.concat([catalog, catalog], ignore_index=True, axis=0)

        events = serialize_seismostats_catalog(catalog)

        assert events[0]['magnitude_value'] == 2.510115344
