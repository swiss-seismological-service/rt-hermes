import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from hermes.io.seismicity import SeismicityDataSource

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


@pytest.mark.usefixtures("prefect")
class TestSeismicityDataSource:

    def test_get_catalog_from_file(self):
        qml_path = os.path.join(MODULE_LOCATION, 'quakeml.xml')

        starttime = datetime.fromisoformat('2021-12-25T00:00:00')
        endtime = datetime.fromisoformat('2021-12-30T12:00:00')

        catalog = SeismicityDataSource.from_file(qml_path, starttime, endtime)

        assert len(catalog.data) == 2

        assert len(catalog.get_data(starttime
                   + timedelta(days=1), endtime)) == 1

        assert len(catalog.get_data(endtime=endtime
                   - timedelta(days=1))) == 1

        assert catalog.get_quakeml() == catalog.data.to_quakeml()

    @patch('seismostats.FDSNWSEventClient._get_batch_params')
    @patch('hermes.io.datasource.requests.get')
    def test_get_catalog_from_fdsnws(self, mock_get, params):

        with open(os.path.join(MODULE_LOCATION, 'quakeml.xml'), 'r') as f:
            answer = Mock(text=f.read(), status_code=200)

        params.return_value = [
            {'starttime': '2021-12-25T00:00:00',
             'endtime': '2022-12-25T00:00:00',
             'limit': 1000,
             'offset': 0},
            {'starttime': '2021-12-25T00:00:00',
             'endtime': '2022-12-25T00:00:00',
             'limit': 1000,
             'offset': 1000}
        ]

        urls = ['https://mock.com?starttime=2021-12-25T00%3A00%3A00&'
                'endtime=2022-12-25T00%3A00%3A00&limit=1000&offset=0',
                'https://mock.com?starttime=2021-12-25T00%3A00%3A00&'
                'endtime=2022-12-25T00%3A00%3A00&limit=1000&offset=1000']
        mock_get.return_value = answer

        base_url = 'https://mock.com'
        starttime = datetime(2021, 12, 25)
        endtime = datetime(2022, 12, 25)
        catalog = SeismicityDataSource.from_ws(
            base_url, starttime, endtime)

        for url in urls:
            mock_get.assert_any_call(url, timeout=300)

        assert len(catalog.data) == 4

    @patch('hermes.io.seismicity.SeismicityDataSource.from_file',
           autocast=True)
    @patch('hermes.io.seismicity.SeismicityDataSource.from_ws',
           autocast=True)
    def test_get_uri_catalog(self,
                             mock_fdsn_source: MagicMock,
                             mock_file_source: MagicMock):

        SeismicityDataSource.from_uri('file:///home/user/file.txt',
                                      datetime(2021, 1, 1),
                                      datetime(2021, 1, 2))

        mock_file_source.assert_called_with('/home/user/file.txt',
                                            datetime(2021, 1, 1),
                                            datetime(2021, 1, 2))

        SeismicityDataSource.from_uri('http://example.com',
                                      datetime(2021, 1, 1),
                                      datetime(2021, 1, 2))

        mock_fdsn_source.assert_called_with('http://example.com',
                                            datetime(2021, 1, 1),
                                            datetime(2021, 1, 2))

        with pytest.raises(ValueError):
            SeismicityDataSource.from_uri('ftp://example.com',
                                          datetime(2021, 1, 1),
                                          datetime(2021, 1, 2))
