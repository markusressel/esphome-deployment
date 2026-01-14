# esphome-deployment

A CLI Tool for managing compilation and deployment of ESPHome Device configurations.

## Features

- Batch-Deploy ESPHome configurations
- Build caching with reproducible builds
- Only upload changed binaries
- Deployment State Tracking via VCS (Git)

# Setup

## Reproducible Builds

For the build and upload caching to work even across multiple machines and builds,
the builds produced by ESPHome need to be made "reproducible". This means that
given the same input, the build process should always produce the exact same output binary,
bit for bit.

Unfortunately, ESPHome does not currently guarantee reproducible builds out of the box, but
there are a couple of small config options we can put into a package and include in all of our
device configurations to help with this.

### `esphome` Section

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

### `esp32` Section

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

Note: The `esp8266` does **not** support or require any special options for reproducible builds at this time.
Only the general `esphome` section as shown above is needed.

## Usage

1. Clone this repository next to your ESPHome configurations
2. Ensure your configurations utilize the reproducible build options as shown above

### Install Dependencies

```bash
python3 -m venv venv
. venv/bin/activate && pip install --upgrade pip poetry
poetry install -P ./esphome-deployment
```

### Compile a single Configuration

```bash
poetry run -P ./esphome-deployment esphome-deployment compile -n "your_epshome_config.yaml"
```

### Upload a single Configuration

```bash
poetry run -P ./esphome-deployment esphome-deployment upload -n "your_epshome_config.yaml"
```