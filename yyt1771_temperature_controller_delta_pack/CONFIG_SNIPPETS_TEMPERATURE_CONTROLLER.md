# Temperature Controller Config Snippets

Add these snippets to the current profile files if equivalent fields do not already exist.

## dev_mock.yaml

```yaml
temperature_controller:
  type: mock
  enabled: true
  initial_temperature_c: 20.0
  ramp_rate_c_per_min: 2.0
  allow_set_target: true
  allow_set_power: true
  initial_target_temperature_c: 45.0
  initial_power_percent: 0.0
  output_enabled: false
```

## dev_offline.yaml

```yaml
temperature_controller:
  type: file
  enabled: false
  temperature_file: ./sample_data/temperature_trace.csv
  loop: false
```

## dev_lab.example.yaml

```yaml
temperature_controller:
  type: serial_ascii
  enabled: true
  port: "REPLACE_WITH_LOCAL_SERIAL_PORT"
  baud_rate: 9600
  bytesize: 8
  parity: N
  stopbits: 1
  timeout_s: 1.0
  write_timeout_s: 1.0
  poll_interval_s: 0.5
  protocol: configured_ascii
  command_set:
    read_current_temperature: null
    read_target_temperature: null
    set_target_temperature: null
    read_power_percent: null
    set_power_percent: null
    set_output_enabled: null
```

Real command strings should be placed in ignored local config, not committed shared config.
