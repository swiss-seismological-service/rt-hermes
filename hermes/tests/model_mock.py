import os
import pickle

from hermes_model import ModelInput, validate_entrypoint
from seismostats import ForecastCatalog

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


@validate_entrypoint(induced=False)
def model_mock(model_input: ModelInput) -> list[ForecastCatalog]:

    with open(MODULE_LOCATION + '/results.pkl', 'rb') as f:
        results = pickle.load(f)

    return [results]
