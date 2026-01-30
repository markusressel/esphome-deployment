# esphome-deployment

A CLI Tool for managing compilation and deployment of ESPHome Device configurations.

## Features

- [x] Batch-Deploy ESPHome configurations
- [x] Build caching with reproducible builds
- [x] Only upload changed binaries
- [x] Deployment State Tracking via VCS (Git)

## Prerequisites

### ESPHome CLI

This tool requires the ESPHome CLI to be installed and available within your system's PATH.
See: https://esphome.io/guides/installing_esphome.html

### Reproducible Builds

For the caching mechanism of esphome-deployment to work across machines,
the firmware images produced by ESPHome need to be made "reproducible". This means that
given the same input, the build process should always produce the exact same output binary,
bit for bit. Unfortunately, ESPHome does not currently guarantee reproducible builds out of the box, but
there are a couple of options to remedy this:

#### `esphome:` Section

> `packages/esphome.yaml`
```yaml
esphome:
  platformio_options:
    build_flags:
      # 1. Prevent warnings for redefining built-in macros
      - -Wno-builtin-macro-redefined
      # 2. Force a static date and time
      - '-D__DATE__="\"Dec 29 2025\""'
      - '-D__TIME__="\"23:00:00\""'
```

See: https://esphome.io/components/esphome/

#### `esp32:` Section

> `packages/chip/esp32-esp-idf.yaml`
```yaml
esp32:
  framework:
    type: esp-idf
    sdkconfig_options:
      # options to ensure reproducible builds (exact binary match)
      CONFIG_APP_REPRODUCIBLE_BUILD: y
      CONFIG_APP_COMPILE_TIME_DATE: n
      CONFIG_APP_EXCLUDE_PROJECT_VER_VAR: y
      CONFIG_APP_EXCLUDE_PROJECT_NAME_VAR: y
```

See: https://esphome.io/components/esp32/

Note: The `esp8266` does **not** support or require any special options for reproducible builds at this time.
Only the general `esphome` section as shown above is needed.

## Setup

1. Create a git repository to track your ESPHome configurations (if you don't have one already)
2. Clone this repository as a git submodule next to your ESPHome configurations
    * e.g. `git submodule add https://github.com/markusressel/esphome-deployment`
3. Ensure your configurations utilize the reproducible build options as shown above
    * e.g. via packages for both ESPHome and ESP32 devices containing the options above
4. Use `poetry` (or any other method of your choice) to run esphome-deployment (see below)

### Install Dependencies

```bash
python3 -m venv venv
. venv/bin/activate && pip install --upgrade pip poetry
poetry install -P ./esphome-deployment
```

## Usage

### Compile ESPHome Firmwares

```bash
poetry run -P ./esphome-deployment esphome-deployment compile
```

Single Configuration:

```bash
poetry run -P ./esphome-deployment esphome-deployment compile -n "your_epshome_config.yaml"
```

### Upload compiled Firmware Images

```bash
poetry run -P ./esphome-deployment esphome-deployment upload
```

Filter by single Configuration:

```bash
poetry run -P ./esphome-deployment esphome-deployment upload -n "your_epshome_config.yaml"
```

### Compile + Upload (Deploy)

```bash
poetry run -P ./esphome-deployment esphome-deployment deploy
```

Single Configuration:

```bash
poetry run -P ./esphome-deployment esphome-deployment deploy -n "your_epshome_config.yaml"
```

## Configuration

### Main configuration

The main configuration for esphome-deployment can be specified in a file named `esphome_deployment.yaml` located next to your ESPHome configurations (within your working
directory).
See [`esphome_deployment.yaml`](esphome_deployment.yaml) for all available options.

### Per-Device configuration

Each ESPHome configuration can optionally contain a `.esphome_deployment:` section (note the leading dot) to adjust the deployment behavior for that specific device.
Example:

```yaml
.esphome_deployment:
  deploy: true

packages:
  esphome: !include packages/esphome.yaml
  chip: !include packages/chip/esp32-esp-idf.yaml

... rest of your esp home config ...
```