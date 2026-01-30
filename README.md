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

## Example run

```bash
$ poetry run -P ./esphome-deployment esphome-deployment deploy -n quinled-an-penta-plus-markus-worktop.yaml                                                                                                                                                                                                                                                                                                                                         0 (0.000s) < 21:50:03
2026-01-30 21:50:05,268 - esphome-deployment - INFO - === esphome-deployment ===
2026-01-30 21:50:05,274 - esphome_deployment.deployment.deployment_coordinator - INFO - Deploying configuration for: quinled-an-penta-plus-markus-worktop
2026-01-30 21:50:05,390 - esphome_deployment.deployment.deployment_coordinator - INFO - Executing esphome with arguments: ('compile', '/home/markus/programming/PycharmProjects/esphome-configs/quinled-an-penta-plus-markus-worktop.yaml')
INFO ESPHome 2026.1.2
INFO Reading configuration /home/markus/programming/PycharmProjects/esphome-configs/quinled-an-penta-plus-markus-worktop.yaml...
... (truncated for brevity) ...
Compiling .pioenvs/markus-worktop/src/esphome/components/api/api_connection.cpp.o
Compiling .pioenvs/markus-worktop/src/esphome/components/api/api_frame_helper.cpp.o
Compiling .pioenvs/markus-worktop/src/esphome/components/api/api_frame_helper_noise.cpp.o
Compiling .pioenvs/markus-worktop/src/esphome/components/api/api_server.cpp.o
Compiling .pioenvs/markus-worktop/src/esphome/components/api/list_entities.cpp.o
Compiling .pioenvs/markus-worktop/src/esphome/components/api/subscribe_state.cpp.o
... (truncated for brevity) ...
INFO Uploading /home/markus/programming/PycharmProjects/esphome-configs/.esphome/build/markus-worktop/.pioenvs/markus-worktop/firmware.bin (872720 bytes)
Uploading: [============================================================] 100% Done...

INFO Upload took 5.28 seconds, waiting for result...
INFO OTA successful
INFO Successfully uploaded program.
2026-01-30 21:50:31,601 - esphome_deployment.deployment.deployment_coordinator - INFO - Successfully uploaded configuration for 'quinled-an-penta-plus-markus-worktop'
```