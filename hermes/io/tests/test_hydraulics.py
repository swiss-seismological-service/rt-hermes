import json
import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from hermes.io.hydraulics import HydraulicsDataSource

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


@pytest.mark.usefixtures("prefect")
class TestHydraulicsDataSource:

    def test_get_catalog_from_file(self):
        hydjson_path = os.path.join(MODULE_LOCATION, 'borehole.json')

        starttime = datetime.fromisoformat('2022-04-19T13:04:00')
        endtime = datetime.fromisoformat('2022-04-19T13:05:00')

        hydraulics = HydraulicsDataSource.from_file(
            hydjson_path, starttime, endtime)

        assert len(hydraulics.get_data()[0]
                   .nloc['16A-32/section_02'].hydraulics) == 60

        hydraulics = HydraulicsDataSource.from_file(
            hydjson_path)

        with open(hydjson_path, 'rb') as f:
            hydjson = json.load(f)

        assert json.loads(hydraulics.get_json()) == [hydjson]

    @patch('hermes.io.datasource.requests.get')
    def test_get_catalog_from_hydws(self, mock_get: MagicMock):

        with open(os.path.join(MODULE_LOCATION, 'borehole.json'), 'r') as f:
            answer = Mock(text=f.read(), status_code=200)

        url = 'https://mock.com?level=hydraulic&starttime=2021-12-25' \
            'T00%3A00%3A00&endtime=2023-12-12T12%3A01%3A03'

        mock_get.return_value = answer

        base_url = 'https://mock.com'
        starttime = datetime(2021, 12, 25)
        endtime = datetime(2023, 12, 12, 12, 1, 3)

        hydraulics = HydraulicsDataSource.from_ws(
            base_url, starttime, endtime)

        mock_get.assert_called_with(url, timeout=300)

        assert len(hydraulics.get_data(
            starttime=datetime(2022, 4, 19, 13, 4, 0),
            endtime=datetime(2022, 4, 19, 13, 5, 0))[0]
            .nloc['16A-32/section_02'].hydraulics) == 60

    @patch('hermes.io.hydraulics.HydraulicsDataSource.from_file',
           autocast=True)
    @patch('hermes.io.hydraulics.HydraulicsDataSource.from_ws',
           autocast=True)
    def test_get_uri_catalog(self,
                             mock_hydws_source: MagicMock,
                             mock_file_source: MagicMock):

        HydraulicsDataSource.from_uri('file:///home/user/file.txt',
                                      datetime(2021, 1, 1),
                                      datetime(2021, 1, 2))

        mock_file_source.assert_called_with('/home/user/file.txt',
                                            datetime(2021, 1, 1),
                                            datetime(2021, 1, 2))
        HydraulicsDataSource.from_uri('http://example.com',
                                      datetime(2021, 1, 1),
                                      datetime(2021, 1, 2))

        mock_hydws_source.assert_called_with('http://example.com',
                                             datetime(2021, 1, 1),
                                             datetime(2021, 1, 2))

        with pytest.raises(ValueError):
            HydraulicsDataSource.from_uri('ftp://example.com',
                                          datetime(2021, 1, 1),
                                          datetime(2021, 1, 2))
