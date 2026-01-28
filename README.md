![pypi](https://img.shields.io/pypi/v/rt-hermes)
[![PyPI - License](https://img.shields.io/pypi/l/rt-hermes)](https://pypi.org/project/rt-hermes/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rt-hermes.svg)](https://pypi.org/project/rt-hermes/)
[![test](https://github.com/swiss-seismological-service/rt-hermes/actions/workflows/tests.yml/badge.svg)](https://github.com/swiss-seismological-service/rt-hermes/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/swiss-seismological-service/rt-hermes/graph/badge.svg?token=RVJFHYLBKA)](https://codecov.io/github/swiss-seismological-service/rt-hermes)

# RT-HERMES - _RealTime Hub for Earthquake foRecasts ManagEment and Scheduling_

©2026 ETH Zurich

## 1. Overview

This project is under active development. The goal is to provide an orchestration and scheduling platform for earthquake forecast models.

### 1.1 Models

This project does not distribute any earthquake forecast models. It is merely a framework to run and schedule earthquake forecast models. The models need to be installed separately. Please look at the [hermes-model](https://github.com/swiss-seismological-service/hermes-model) repository for more information on how to install and use a model with HERMES. Current open source models compatible with HERMES are: [EM1](https://gitlab.seismo.ethz.ch/indu/em1), [HM-1D](https://gitlab.seismo.ethz.ch/indu/hm-1d), [etas](https://github.com/swiss-seismological-service/etas)

### 1.2 Contents
1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Using HERMES](#3-using-hermes)
4. [Advanced: Distributed Workers](#4-advanced-distributed-workers)
5. [Manage the Services](#5-manage-the-services)
6. [Concepts / Configurations](https://github.com/swiss-seismological-service/hermes/blob/main/docs/concepts.md)
7. [Injectionplans](https://github.com/swiss-seismological-service/rt-hermes/blob/main/docs/injectionplan.md)
8. [Datamodel](https://github.com/swiss-seismological-service/rt-hermes/blob/main/docs/datamodel.pdf)

## 2 Installation

### 2.1 Dependencies

Possibly, the following system dependencies are required to install some of the Python dependencies. On a Debian-based system, you can install them using:

```bash
sudo apt-get install build-essential libpq-dev python3-dev python3-venv
```

Also, Python 3.12 or higher is required.

### 2.2 Installation Methods
There are mainly 3 possible installation methods to get started with HERMES:
1. [User Installation including the services](#23-user-installation-including-services)
2. [User Installation of the CLI only](#24-user-installation-of-the-cli-only), assuming services and credentials are already provided
3. [Development installation](#25-development-installation), if you want to contribute to the development of HERMES

### 2.3 (Option 1) User Installation including Services

This installation instruction is merely a recommendation for a user of the software. Depending on your preferences and knowledge, you are free to choose a different setup.

This section describes the installation from scratch, including the required services. If a full installation of the servicecs is already provided to you, you can go to [2.2](#22-install-hermes).

#### 2.3.1 Install Docker

Follow the instructions [here](https://docs.docker.com/get-docker/)

#### 2.3.2 Setup
We opt for the following project structure:

```bash
├── hermes-project/     # your project folder
    ├── .env            # environment file
    ├── env/            # virtual environment
    ├── rt-hermes/      # the cloned repository
    └── models/         # contains the installed models
        ├── ml1/
        └── em1/
```

This allows us to have the software code locally available, while keeping the project files separate. Use the following steps to set up the environment.

Create the project folder and set up a virtual environment:
```bash
# create and go to folder hermes-project
mkdir hermes-project && cd hermes-project
python3 -m venv env # python>=3.12 is required
source env/bin/activate
pip install -U pip wheel setuptools
```

Clone the `rt-hermes` repository and the models you want to use:
```bash
# inside the hermes-project/ folder
git clone https://github.com/swiss-seismological-service/rt-hermes.git
# create and go to models/ folder
mkdir models && cd models
git clone https://gitlab.seismo.ethz.ch/indu/em1.git
# optionally, clone other models too
cd ..
```

Install the `rt-hermes` package in editable mode along with the development dependencies, as well as the models:
```bash
# inside the hermes-project/ folder
pip install -e ./rt-hermes[dev]
pip install -e ./models/em1
```

#### 2.3.3 Settings
Copy the example environment settings to a new `.env` file:

```bash
# inside the hermes-project/ folder
cp rt-hermes/.env.example .env
```

The settings in the `.env` file work out of the box in a local setup, but are not secure. Please change the credentials, ports and connection strings in the `.env` file if deploying in an externally accessible environment.


#### 2.3.4 Start the services
You can now create the Docker services for the Prefect Server and the PostgreSQL database using the following command:

```bash
# go to the rt-hermes/ folder
cd rt-hermes
docker compose --env-file ../.env -f compose-prefect.yaml -f compose-database.yaml up -d
cd ..
```

#### 2.3.5 Initialize the database and test the setup
To verify that the installation was successful, you can initialize the database and run the tests:

```bash
# inside the hermes-project/ folder, with the virtual environment activated
hermes db initialize
pytest rt-hermes/hermes
```

Any further `CLI` commands should be run from within the `hermes-project/` folder with the virtual environment activated.


### 2.4 (Option 2) User Installation of the CLI only

If the services are already provided to you, you can simply install the `rt-hermes` package in your virtual environment.


#### 2.4.1 Setup virtual environment and install rt-hermes
Create a virtual environment using Python 3.12 or higher:

```bash
mkdir hermes-project && cd hermes-project
python3 -m venv env
source env/bin/activate
pip install -U pip wheel setuptools
pip install rt-hermes
```

#### 2.4.2 Settings
Copy the example environment settings from the `rt-hermes` package into a new `.env` file and adjust them to your provided services.

You can find the template of the `.env`file [here](https://github.com/swiss-seismological-service/rt-hermes/blob/main/.env.example).

```bash
touch .env
# copy the content of the .env.example file into the .env file
```

#### 2.4.3 Test the setup
Test the connectivity to the services by running:

```bash
hermes db test-connection
hermes projects list
```

### 2.5 (Option 3) Development Installation
If you want to contribute to the development of HERMES, I suggest the following structure:

```bash
.
├── rt-hermes/          # the cloned repository, working directory
    ├── .env            # environment file
    └── env/            # virtual environment
└── em1/                # cloned model repository
```

#### 2.5.1 Setup
Clone the `rt-hermes` repository and the models you want to use:
```bash
git clone https://github.com/swiss-seismological-service/rt-hermes.git
git clone https://gitlab.seismo.ethz.ch/indu/em1.git
# optionally, clone other models too
```

Create a virtual environment.
```bash
# go to the rt-hermes/ folder
cd rt-hermes
python3 -m venv env # python>=3.12 is required
source env/bin/activate
pip install -U pip wheel setuptools
```

Install the `rt-hermes` package in editable mode along with the development dependencies, as well as the models:
```bash
# inside the rt-hermes/ folder
pip install -e ./rt-hermes[dev]
pip install -e ../em1
```

#### 2.5.2 Settings
Copy the example environment settings into a new `.env` file and adjust them to your needs.

```bash
# inside the rt-hermes/ folder
cp .env.example .env
```

#### 2.5.3 Start the services
You can now create the Docker services for the Prefect Server and the PostgreSQL database using the following command:

```bash
# inside the rt-hermes/ folder
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
```

#### 2.5.4 Initialize the database and test the setup
To verify that the installation was successful, you can initialize the database and run the tests:

```bash
# inside the rt-hermes/ folder, with the virtual environment activated
hermes db initialize
pytest hermes
pytest web
```

## 3 Using HERMES
Basically, you should now be able to run models using HERMES. If you have your own models and usecases, go ahead and configure them according to the [concepts documentation](https://github.com/swiss-seismological-service/hermes/blob/main/docs/concepts.md).

If you would like to try out HERMES with an example configuration and data, follow the steps below.


### 3.1 Start with example configuration and data

You can start with an example configuration and data to get a feel for how HERMES works. Some example configuration is located in the `rt-hermes/examples` folder. Copy the whole `examples/` folder to your working directory (the same directory where you have the `.env` file), if it is not already there.

### 3.2 Adjust the example configuration
You need to adjust the example configuration files to your local setup. In particular, you need to update the paths to the data sources.

Update the absolute path `fdsnws_url` in `examples/induced/forecastseries.json` to your local path of the `examples/induced` folder. Also, to use the scforge HYDWS service, you need to be connected to the ETH network or a VPN.

### 3.3 Load an example configuration
The CLI can be used to interact with the HERMES service. For a list of available commands, run `hermes --help`. Most commands have a `--help` option to show the available options.

```bash
hermes projects create project_induced --config examples/induced/project.json
hermes forecastseries create fs_induced --config examples/induced/forecastseries.json --project project_induced
hermes injectionplans create default --forecastseries fs_induced --file examples/induced/multiply_template.json
hermes models create em1 --config examples/induced/model_config.json
```

Most setting should be self-explanatory, but more information can be found in the [concepts documentation](https://github.com/swiss-seismological-service/hermes/blob/main/docs/concepts.md).

A more detailed of the InjectionPlan configuration can be found [here](https://github.com/swiss-seismological-service/hermes/blob/main/docs/injectionplan.md).

### 3.4 Run a single forecast using the CLI

```
hermes forecasts run fs_induced --start 2022-04-21T15:00:00 --end 2022-04-21T18:00:00 --local
```

This starts a single forecast directly on the local machine.

### 3.5 (Optional) Schedule forecasts or execute "replays".

To use advanced features like scheduling, it is necessary to start a process which "serves" the forecastseries. This will be a long-running process which will execute forecasts as they are requested by the schedule or by the CLI, so just let the process run in a terminal, and open a new terminal to execute further commands.

```
hermes forecastseries serve fs_induced --concurrency-limit=2
```

Depending on your model, you need to control how many modelruns are executed in parallel, you can do that by specifying the `--concurrency-limit` option. Please consider, that also the requesting of the input data can become a limiting factor if you are requesting a lot of data at the same time (eg. requests to an FDSNWS).

Once this process is running, you can "send" a forecast to the service using the above command in a new terminal without the `--local` flag.

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

**Note** that a schedule can either lie in the past, the future, or both. The `catchup` command will only execute forecasts in the past, while the service will automatically execute forecasts in the future.


### 3.6 Results
To view the forecasts and modelruns, currently only the webservice is available. The available endpoints are listed in the API documentation: [http://localhost:8000/docs](http://localhost:8000/docs).

A quick description of the way to traverse the API is as follows:
To view the `Projects`, you can navigate to the following URL: [http://localhost:8000/v1/projects](http://localhost:8000/v1/projects). Copy the `oid` of the project you'd like to access.

To find the correct `Forecastseries`, you can navigate to the following URL: [http://localhost:8000/v1/projects/<project_oid>/forecastseries](http://localhost:8000/v1/projects/<project_oid>/forecastseries). Again, copy the `oid` of the `ForecastSeries`.

To view the `Forecasts` and `ModelRuns`, you can navigate to the following URL: [http://localhost:8000/v1/forecastseries/<forecastseries_oid>/forecasts](http://localhost:8000/v1/forecastseries/<forecastseries_oid>/forecasts).

The results of the modelruns can be directly downloaded from the webservice. This API is still under development and will be improved in the future. The results can be downloaded from the following URL: [http://localhost:8000/v1/modelruns/<modelrun_oid>/results](http://localhost:8000/v1/modelruns/<modelrun_oid>/results).

### 3.7 Python Client

A Python client library is provided for easier access to the RT-HERMES data and results. It can be installed using pip:

```bash
pip install hermes-client
```

And the documentation can be found here: [https://hermes-client.readthedocs.io](https://hermes-client.readthedocs.io)


### 3.6 Debugging

Once you have the `oid` of a modelruns, you can use that to more easily debug the runs. You can download the exact configuration and input files the modelrun used. Navigate to the following URL: [http://localhost:8000/v1/modelruns/<modelrun_oid>/input](http://localhost:8000/v1/modelruns/<modelrun_oid>/input) to download the input files, which you can then directly use to run the model manually outside of HERMES for debugging purposes.

### 3.7 Long Running Services
To continuously serve forecasts, on eg. a server, you can set up a long running service using systemd. If you do this on the same machine as the services run, this only requires to daemonize the serve command. If you'd rather have the model run on a different machine, please refer to [4. Distributed Workers](#4-advanced-distributed-workers) in the next chapter.

Create a new service file, e.g. `/etc/systemd/system/hermes-forecastseries.service` with the following content:

```ini
[Unit]
Description=Prefect Serve Forecastseries
After=network.target

[Service]
User=username
WorkingDirectory=/path/to/rt-hermes
Environment="PATH=/path/to/rt-hermes/env/bin"
ExecStart=/path/to/rt-hermes/env/bin/hermes forecastseries serve fs_induced --concurrency-limit 4

[Install]
WantedBy=multi-user.target
```

Replace `username` with your actual username, and adjust the paths accordingly.

Enable and start the service:

```bash
sudo systemctl enable hermes-forecastseries.service
sudo systemctl start hermes-forecastseries.service
```

Check the status of the service and view the logs:

```bash
sudo systemctl status hermes-forecastseries.service
sudo journalctl -u hermes-forecastseries.service -f
```

> [!WARNING]
> Do not forget to restart the service, if you change the configuration or the code.

## 4. (Advanced) Distributed Workers

HERMES supports the execution of models on different machines. This allows to more easily scale the execution of models.

> [!IMPORTANT]
> Prefect offers different ways of running distributed workers. The most simple way is to *serve a flow*, which is described in the previous sections. This has some limitations, and is less scalable. However, for the current version of HERMES, we chose this approach for simplicity and ease of use. 

To set up a long running worker, you need to install rt-hermes on the worker machine, and then daemonize the following command:

```bash
hermes forecastseries serve fs_induced --concurrency-limit=...
```

### 4.1 Installation

You could also install it from PyPI, but here we describe the installation from source, which is more flexible for development and debugging.

Clone the `rt-hermes` repository and the models you want to use:
```bash
git clone https://github.com/swiss-seismological-service/rt-hermes.git
git clone https://gitlab.seismo.ethz.ch/indu/em1.git
```

Install the `rt-hermes` package in editable mode along with the development dependencies, as well as the models:
```bash
cd rt-hermes
python3 -m venv env
source env/bin/activate
pip install -U pip wheel setuptools
pip install -e ./rt-hermes[dev]
pip install -e ../em1
```

### 4.2 Settings
A worker only needs minimal settings to connect to the Prefect server and the database. Copy the example worker environment settings into a new `.env` file and adjust them to your needs.

```bash
cp .env.worker.example .env
```

Replace the `PREFECT_API_URL=http://host-machine:4200/api` with the actual host name or IP address of the machine running the Prefect server.

### 4.3 Create the worker service
Create a new service file for the worker, e.g. `/etc/systemd/system/hermes-worker.service` with the following content:

```ini
[Unit]
Description=Prefect Serve Forecastseries
After=network.target

[Service]
User=username
WorkingDirectory=/path/to/rt-hermes
Environment="PATH=/path/to/rt-hermes/env/bin"
ExecStart=/path/to/rt-hermes/env/bin/hermes forecastseries serve fs_induced --concurrency-limit 4

[Install]
WantedBy=multi-user.target
```

Replace `username` with your actual username, and adjust the paths accordingly.

Enable and start the service:

```bash
sudo systemctl enable hermes-worker.service
sudo systemctl start hermes-worker.service
```

Check the status of the service and view the logs:

```bash
sudo systemctl status hermes-worker.service
sudo journalctl -u hermes-worker.service -f
```

> [!WARNING]
> Do not forget to update the repository, and restart the service, if you change the configuration or the code, only updating the code on the server will NOT update the workers automatically.


## 5 Manage the Services

### 5.1 Update the services

Inside the cloned `rt-hermes`repository folder, update the repository, then the docker containers, make sure you have the correct path to the `.env` file:

```bash
cd rt-hermes
git pull
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
prefect server database upgrade -y
hermes db upgrade
```

### 5.2 Update the CLI

If you installed the cli from pip, you can update it by running the following command inside your virtual environment:

```bash
pip install -U rt-hermes
```

If you installed it in editable mode from the cloned repository, you can update it by pulling the latest changes from the repository:

```bash
cd rt-hermes
git pull
```

### 5.3 Reinstall the services

If you want to update the services and would like a clean install or/and don't care about the existing data, you can do so by completely removing the existing containers and volumes, pulling the latest changes, and then starting the services again.

Make sure you have the correct path to the `.env` file:

```bash
docker compose -f compose-prefect.yaml -f compose-database.yaml down -v
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d
```

### 5.4 Major Database Upgrades

In case of major upgrades to the database (eg. PostgreSQL version upgrades), it might be necessary to manually migrate the data. Such upgrades should not happen often. Please contact the maintainers in such a case.

As reference, a quick upgrade path is described below:

```bash
# -U specifying the user, -d specifying the database
pg_dump -h localhost -p 5434 -U postgres -d postgres > backup.sql

# update the containers
docker compose -f compose-prefect.yaml -f compose-database.yaml down -v
docker compose --env-file .env -f compose-prefect.yaml -f compose-database.yaml up -d

# restore the database
psql -h localhost -p 5432 -U postgres -d postgres < backup.sql

# run the database upgrades
hermes db upgrade
```









