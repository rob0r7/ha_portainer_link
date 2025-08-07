# Update Available Sensor

## Overview

The **Update Available Sensor** is a new binary sensor that detects when Docker container images have updates available. This feature helps you stay informed about which containers might need updates.

## How it Works

The sensor checks for updates using several methods:

1. **Latest Tag Detection**: If a container uses a `:latest` tag, the sensor assumes updates might be available
2. **Multiple Tag Analysis**: If an image has multiple tags (including version tags), it may indicate newer versions
3. **Creation Date Comparison**: Compares container creation date with image creation date

## Features

- **Binary Sensor**: Shows `on` when updates are available, `off` when up to date
- **Dynamic Icons**: Uses `mdi:update` when updates are available, `mdi:update-disabled` when not
- **Pull Update Button**: Automatically appears when updates are available (with download icon)
- **Automatic Updates**: Refreshes status periodically with other sensors
- **Error Handling**: Gracefully handles API errors and network issues

## Usage

The sensor and button are automatically created for each container when you set up the integration. You can:

- **Monitor**: Add the sensor to your dashboard to see which containers need updates
- **Update**: Use the pull button to download the latest image when updates are available
- **Automate**: Use the sensor in automations to notify you when updates are available
- **Integrate**: Combine with other sensors for comprehensive container monitoring

## Example Automation

```yaml
automation:
  - alias: "Notify when container updates are available"
    trigger:
      platform: state
      entity_id: binary_sensor.container_name_update_available
      to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Container Update Available"
          message: "{{ trigger.entity_id }} has updates available"
```

## Example Button Usage

The pull update button will automatically appear in the device controls when updates are available. You can:

- **Manual Update**: Click the button to pull the latest image
- **Dashboard Integration**: Add the button to your dashboard for quick access
- **Conditional Display**: The button only shows when updates are actually available

## Limitations

- **Registry Integration**: Currently uses heuristics rather than direct registry queries
- **Latest Tags**: Assumes `:latest` tags always have potential updates
- **Version Detection**: Basic version tag detection (v2, v3, v4, v5)

## Future Enhancements

- Direct Docker registry integration
- More sophisticated version comparison
- Support for private registries
- Automatic update triggering via Portainer webhooks

## Technical Details

The sensor uses the Portainer API to:
1. Inspect container details
2. Retrieve image information
3. Analyze image tags and metadata
4. Determine update availability

This provides a foundation for more advanced update management features in the future.
