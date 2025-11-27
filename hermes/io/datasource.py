import logging
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar

import requests
from prefect import get_run_logger, task

from hermes.utils.url import add_query_params

T = TypeVar('T')


class DataSource(ABC, Generic[T]):
    def __init__(self,
                 data: T | None = None) \
            -> None:
        """
        Provides a common interface to access seismic event
        data from different sources.

        Should in most cases be initialized using class methods
        according to the source of the data.

        Args:
            catalog: Catalog object.
            starttime: Start time of the catalog.
            endtime: End time of the catalog

        Returns:
            T object instance containing the data.
        """
        try:
            self.logger = get_run_logger()
        except BaseException:
            self.logger = logging.getLogger('prefect.hermes')
        self.data = data

    @classmethod
    def from_uri(cls,
                 uri,
                 starttime: datetime | None = None,
                 endtime: datetime | None = None) -> 'DataSource':

        if uri.startswith('file://'):

            file_path = urllib.parse.urlparse(uri)
            file_path = urllib.parse.unquote(file_path.path)
            data = cls.from_file(file_path, starttime, endtime)
        elif uri.startswith('http://') or uri.startswith('https://'):
            data = cls.from_ws(uri, starttime, endtime)
        else:
            raise ValueError(
                f'URI scheme of data source not supported: {uri}')

        return data

    @classmethod
    @abstractmethod
    @task
    def from_ws(self):
        pass

    @classmethod
    @abstractmethod
    @task
    def from_file(self):
        pass

    @task(name='ws-request',
          retries=3,
          retry_delay_seconds=[3, 9, 27],
          retry_jitter_factor=0.5)
    def _request_text(self, url: str, timeout: int = 300, **kwargs) \
            -> tuple[str, int]:
        """
        Request text from a URL and raise for status.

        Args:
            url: URL to request.
            timeout: Timeout for the request.

        Returns:
            response text, status code.
        """

        for key, value in kwargs.items():
            if isinstance(value, datetime):
                kwargs[key] = value.strftime('%Y-%m-%dT%H:%M:%S')

        url = add_query_params(url, **kwargs)

        self.logger.info(f'Requesting text from {url}.')

        response = requests.get(url, timeout=timeout)

        response.raise_for_status()

        return response.text, response.status_code
