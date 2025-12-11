![pypi](https://img.shields.io/pypi/v/rt-hermes)
[![PyPI - License](https://img.shields.io/pypi/l/rt-hermes)](https://pypi.org/project/rt-hermes/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rt-hermes.svg)](https://pypi.org/project/rt-hermes/)
[![test](https://github.com/swiss-seismological-service/rt-hermes/actions/workflows/tests.yml/badge.svg)](https://github.com/swiss-seismological-service/rt-hermes/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/swiss-seismological-service/rt-hermes/graph/badge.svg?token=RVJFHYLBKA)](https://codecov.io/github/swiss-seismological-service/rt-hermes)

# RT-HERMES - *RealTime Hub for Earthquake foRecasts ManagEment and Scheduling*
©2025 ETH Zurich

## 1. Overview
This project is under active development. The goal is to provide an orchestration and scheduling platform for earthquake forecast models. 

For v0 of the project, see the [gitlab repository](https://gitlab.seismo.ethz.ch/indu/rt-ramsis)

### 1.2 Caveat
This project does not distribute any earthquake forecast models. It is merely a framework to run and schedule earthquake forecast models. The models need to be installed separately. Please look at the [hermes-model](https://github.com/swiss-seismological-service/hermes-model) repository for more information on how to install and use a model with HERMES.

## 2. Installation
This installation instruction is merely a recommendation for a user of the software. Depending on your preferences and knowledge, you are free to choose a different setup.

To use the software, you need to have a correctly configured Prefect Server installation as well as a PostgreSQL database. You can install them using Docker Compose as described in section [2.1](#21-installation-of-the-services). If there is already such an installation provided, you can skip to section [2.2](#22-install-hermes).


### 2.1 Installation of the services.

#### 2.1.1 Install Docker
Follow the instructions [here](https://docs.docker.com/get-docker/)

#### 2.1.2 Clone the repository
First you need to clone the repository. This will create a folder called `rt-hermes` in your current directory.
```
git clone https://github.com/swiss-seismological-service/rt-hermes.git
cd rt-hermes
```

#### 2.1.3 Configure environment file
The `.env` file is used to configure the Prefect Server and the PostgreSQL database. It contains sensitive information such as passwords and connection strings. You can create a copy of the example file with the following command:
```
cp .env.example .env
```
As a quick test setup, the configuration works as is, but is not secure. Please change the credentials, ports and connection strings in the .env file.

#### 2.1.4 Create the Docker services
You can now create the Docker services for the Prefect Server and the PostgreSQL database using the following command:
```
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
```
You can now access the Prefect Server at [http://localhost:4200](http://localhost:4200) and the webservice at [http://localhost:8000/docs](http://localhost:8000/docs).

**Note:** Using multiple `-f` flags ensures both services share the same Docker network for proper inter-service communication.


### 2.2 Install HERMES

#### 2.2.0 Prerequisites
If you already followed Section [2.1](#21-installation-of-the-services), you can create a new folder next to the cloned `rt-hermes` repository to create your project.  
If you have a Service installation provided, but would like to use the examples provided in the repository, you can still clone the repository to get the examples and the template env file:
```
git clone https://github.com/swiss-seismological-service/rt-hermes.git
```

#### 2.2.1 Install Python and a virtual environment
It is strongly recommended to use a virtual environment. This will ensure that the dependencies are isolated from your system Python installation.
```
mkdir hermes-project && cd hermes-project
python3 -m venv env # python3.12 is required
source env/bin/activate
pip install -U pip wheel setuptools
```

#### 2.2.2 Dependencies
Possibly, the following system dependencies are required to install some of the Python dependencies. On a Debian-based system, you can install them using:
```
sudo apt-get install build-essential libpq-dev python3-dev
```

#### 2.2.3 Install HERMES
Install Hermes from the Python Package Index
```
pip install rt-hermes
```

### 2.2.4 Configure the environment file
For HERMES to find the correct Prefect Server and PostgreSQL database, you need to create a `.env` file in the root of your project. You can use the example file provided in the repository:

```
# Assuming you have cloned the repository into the current directorys parent
cp ../rt-hermes/.env.example .env
```
Use the credentials defined in section [2.1](#21-installation-of-the-services) or the ones provided to you by your admin.

#### 2.2.5 Use the CLI
The main usage of HERMES is currently via CLI


#### 2.2.6 Install the models
To run models, you need to have them installed locally. You can, for example, clone them into a subdirectory and install from there.
```
git clone https://gitlab.seismo.ethz.ch/indu/em1.git models/em1
git clone https://github.com/swiss-seismological-service/etas.git models/etas

pip install -e models/em1
pip install -e models/etas
```

## 3 Run models
The models can be run using the CLI.

### 3.1 Start with example configuration and data
You can start with an example configuration and data to get a feel for how HERMES works. The example configuration is located in the `examples/induced` folder. You can copy it to your project directory using the following command, assuming again you have the repository cloned in the parent directory:
```
cp -r ../rt-hermes/examples .
```
> [!IMPORTANT]
> Update the absolute path `fdsnws_url` in `examples/induced/forecastseries.json` to your local path of the `examples/induced` folder. Also, to use the scforge HYDWS service, you need to be connected to the ETH network or a VPN.

### 3.2 Initialize the database
```
hermes db initialize
```
This only needs to be done once. In case you want to delete all data and start from scratch, you can run `hermes db downgrade -y` and then `hermes db initialize` again.

### 3.3 Load an example configuration
```
hermes projects create project_induced --config examples/induced/project.json
hermes forecastseries create fs_induced --config examples/induced/forecastseries.json --project project_induced
hermes injectionplans create default --forecastseries fs_induced --file examples/induced/multiply_template.json
hermes models create em1 --config examples/induced/model_config.json
```

The CLI can be used to interact with the HERMES service. For a list of available commands, run `hermes --help`. Most commands have a `--help` option to show the available options.

Most setting should be self-explanatory, but more information can be found in the [concepts documentation](https://github.com/swiss-seismological-service/hermes/blob/main/docs/concepts.md).

A more detailed of the InjectionPlan configuration can be found [here](https://github.com/swiss-seismological-service/hermes/blob/main/docs/injectionplan.md).

### 3.4 Run a single forecast using the CLI
```
hermes forecasts run fs_induced --start 2022-04-21T15:00:00 --end 2022-04-21T18:00:00 --local
```
This starts a single forecast directly on the local machine. 

### 3.5 (Optional) Schedule forecasts or execute "replays".
To use advanced features like scheduling, it is necessary to start a process which "serves" the forecastseries. 
```
hermes forecastseries serve fs_induced
```

Depending on your model, you need to control how many modelruns are executed in parallel, you can do that by specifying the `--concurrency-limit` option which is by default set to 3. Please consider, that also the requesting of the input data can become a limiting factor if you are requesting a lot of data at the same time (eg. requests to an FDSNWS).

```
hermes forecastseries serve fs_induced --concurrency-limit 1
```

Once this process is running, you can "send" a forecast to the service using the above command without the `--local` flag.  

```
hermes forecasts run fs_induced --start 2022-04-21T15:00:00 --end 2022-04-21T18:00:00
```
This will again execute a single forecast, but this time it will be executed by the service. This now allows us to create a schedule for the forecastseries, which will automatically execute forecasts at the specified times. More information about the schedule settings can be found [here](https://github.com/swiss-seismological-service/hermes/blob/main/docs/concepts.md#forecast-series-scheduling).

```
hermes schedules create fs_induced --config examples/induced/schedule_replay.json
```
This schedule specifies forecasts in the past. Accordingly, no future forecasts will be executed, but the `catchup` command can be used to execute all forecasts as a "replay".
```
hermes schedules catchup fs_induced
```

__Note__ that a schedule can either lie in the past, the future, or both. The `catchup` command will only execute forecasts in the past, while the service will automatically execute forecasts in the future.

### 3.6 Debugging
To view the forecasts and modelruns, currently only the webservice is available. The available endpoints are listed in the API documentation: [http://localhost:8000/docs](http://localhost:8000/docs).

A quick description of the way to traverse the API is as follows:
To view the `Projects`, you can navigate to the following URL: [http://localhost:8000/v1/projects](http://localhost:8000/v1/projects). Copy the `oid` of the project you'd like to access.

To find the correct `Forecastseries`, you can navigate to the following URL: [http://localhost:8000/v1/projects/<project_oid>/forecastseries](http://localhost:8000/v1/projects/<project_oid>/forecastseries). Again, copy the `oid` of the `ForecastSeries`.

To view the `Forecasts` and `ModelRuns`, you can navigate to the following URL: [http://localhost:8000/v1/forecastseries/<forecastseries_oid>/forecasts](http://localhost:8000/v1/forecastseries/<forecastseries_oid>/forecasts).

Once you have the `oid` of the models, you can use that to more easily debug the models. You can download the exact configuration and input files the modelrun used. Navigate to the following URL: [http://localhost:8000/v1/modelruns/<modelrun_oid>/input](http://localhost:8000/v1/modelruns/<modelrun_oid>/input) to download the input files.

### 3.7 Results

The results of the modelruns can be directly downloaded from the webservice. This API is still under development and will be improved in the future. The results can be downloaded from the following URL: [http://localhost:8000/v1/modelruns/<modelrun_oid>/results](http://localhost:8000/v1/modelruns/<modelrun_oid>/results).

### 3.8 Python Client

A Python client library is provided for easier access to the RT-HERMES data and results. It can be installed using pip:
```bash
pip install hermes-client
```
A documentation is available [here](https://github.com/swiss-seismological-service/hermes-client.git)


## 4 Update
### 4.1 Update the services
Inside the cloned repository folder, update the docker containers:

```bash
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
prefect server database upgrade -y
hermes db upgrade
```

### 4.2 Update the library
If you want to update the library, you can do so by running the following command inside your virtual environment:

```bash
pip install -U rt-hermes
```

If you need to update the hermes database too (if your admin has not done that already), you can run the following command:
```bash
hermes db upgrade
```

### 4.3 Reinstall the services

If you want to update the services and would like a clean install or/and don't care about the existing data, you can do so by completely removing the existing containers and volumes, pulling the latest changes, and then starting the services again.

```bash
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml down -v
docker compose -f compose-prefect.yaml pull
docker compose -f compose-database.yaml pull
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
```

