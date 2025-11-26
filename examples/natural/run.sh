source env/bin/activate
hermes db downgrade -y
hermes db initialize
hermes projects create project_natural --config examples/natural/project.json
hermes forecastseries create fs_natural --config examples/natural/forecastseries.json --project project_natural
hermes models create etas --config examples/natural/model_config.json
hermes forecasts run fs_natural --start 2024-12-01T00:00:00 --end 2024-12-31T00:00:00 --local
deactivate