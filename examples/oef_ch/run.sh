source env/bin/activate
hermes db downgrade -y
hermes db initialize
hermes projects create OEF_Switzerland --config examples/oef_ch/project.json
hermes forecastseries create SuiETAS_daily --config examples/oef_ch/forecastseries.json --project OEF_Switzerland
hermes models create SuiETAS --config examples/oef_ch/model_config.json
# hermes forecasts run fs_natural --start 2024-12-01T00:00:00 --end 2024-12-31T00:00:00 --local
deactivate