source env/bin/activate
hermes db downgrade -y
hermes db initialize
hermes projects create project_induced --config examples/induced/project.json
hermes forecastseries create fs_induced --config examples/induced/forecastseries.json --project project_induced
hermes injectionplans create double --forecastseries fs_induced --file examples/induced/multiply_template.json
hermes injectionplans create constant --forecastseries fs_induced --file examples/induced/multiply_template_2.json
hermes models create em1 --config examples/induced/model_config.json
hermes models create em1_2 --config examples/induced/model_config_2.json
hermes forecasts run fs_induced --start 2022-04-21T15:00:00 --end 2022-04-21T18:00:00 --local
hermes forecasts run fs_induced --start 2022-04-21T16:00:00 --end 2022-04-21T18:00:00 --local
hermes forecasts run fs_induced --start 2022-04-21T17:00:00 --end 2022-04-21T18:00:00 --local
deactivate