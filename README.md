# HA Portainer Link

A Home Assistant integration for managing Docker containers and stacks through Portainer.

## Features

- **Container Management**: Start, stop, restart containers
- **Stack Management**: Manage Docker Compose stacks
- **Resource Monitoring**: CPU, memory, and uptime sensors
- **Update Detection**: Check for available container updates
- **Integration Modes**: Choose from Lightweight, Standard, Full, or Custom modes
- **Flexible Configuration**: Support for different Portainer setups and environments

## Installation

1. Copy the `custom_components/ha_portainer_link` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "HA Portainer Link" and add it

## Configuration

### Basic Setup

1. **Portainer URL**: Enter the full Portainer URL (e.g., `https://192.168.0.6:9443` or `http://192.168.0.6:9000`)
2. **Authentication**: Use either username/password or API key
3. **Endpoint ID**: Docker endpoint ID (usually 1)
4. **SSL Verification**: Automatically determined based on connection success

### Integration Modes

#### **Lightweight Mode**
- Minimal functionality for performance-sensitive environments
- Container status sensors and start/stop switches (always available)
- 10-minute update intervals
- No resource monitoring or stack view

#### **Standard Mode**
- Balanced functionality for most common use cases
- Stack view, resource sensors, version tracking, update checks
- Container start/stop switches (always available)
- 5-minute update intervals
- Moderate resource usage

#### **Full Mode**
- Complete functionality with all features enabled
- Everything including container logs and bulk operations
- Container start/stop switches (always available)
- 3-minute update intervals
- Comprehensive monitoring

#### **Custom Mode**
- User-defined feature selection
- Granular control over every feature toggle
- Configurable update intervals and feature sets

### Feature Toggles

**Core Features** (Always Available):
- Container status sensors
- Container start/stop switches

**Optional Features**:
- **Stack View**: Stack clustering and management
- **Resource Sensors**: CPU, memory, uptime monitoring
- **Version Sensors**: Current and available version tracking
- **Update Sensors**: Update availability detection
- **Container Buttons**: Restart and pull update buttons
- **Stack Buttons**: Stack control buttons
- **Bulk Operations**: Start/stop all containers
- **Container Logs**: Log viewing functionality

## Advanced Configuration

### Rate Limiting
- **Cache Duration**: How long to cache update check results (1-24 hours)
- **Rate Limit Checks**: Maximum update checks per period (10-100)
- **Rate Limit Period**: Time period for rate limiting (1-24 hours)

### Performance Tuning
- **Update Interval**: How often to refresh data (1-60 minutes)
- **SSL Verification**: Enable/disable for different environments
- **Timeout**: Request timeout in seconds

## Troubleshooting

### Connection Issues
- **Invalid URL**: Ensure the URL includes the full scheme and port (e.g., `https://192.168.0.6:9443`)
- **SSL Errors**: SSL verification is automatically determined - the integration will try different approaches
- **Authentication**: Verify username/password or API key

### Performance Issues
- **High Resource Usage**: Switch to Lightweight mode
- **Slow Updates**: Increase update interval
- **Rate Limiting**: Adjust cache duration and rate limits

### Feature Issues
- **Missing Sensors**: Check if the feature is enabled in your integration mode
- **Stack Clustering**: Ensure stack view is enabled
- **Update Detection**: Verify update sensors are enabled

## Recent Updates

### Version 0.3.3
- **Simplified Configuration**: Changed to accept full Portainer URL directly (e.g., `https://192.168.0.6:9443`)
- **Eliminated URL Construction**: Removed complex host/port parsing logic to prevent connection issues
- **Better User Experience**: Clearer input field description and validation
- **Fixed Uptime Sensor**: Corrected uptime calculation to use actual container start time instead of stats timestamp
- **Container Switches Always Available**: Made container start/stop switches core functionality available in all integration modes
- **Automatic SSL Verification**: SSL verification is now automatically determined based on connection success

### Version 0.3.2
- **Bug Fixes**: Fixed URL construction issues causing connection errors
- **Migration Support**: Added migration handler for existing configurations
- **Deprecated Code**: Fixed deprecated options flow pattern
- **Integration Modes**: Complete implementation of lightweight, standard, full, and custom modes
- **Feature Toggles**: Granular control over all features
- **Performance Optimization**: Reduced API calls in lightweight mode

### Version 0.3.0
- **Architecture Overhaul**: Implemented DataUpdateCoordinator pattern
- **Modular API**: Split into specialized API classes
- **Base Entity Classes**: Improved code reusability
- **Stack Clustering**: Automatic container grouping by Docker Compose labels
- **Rate Limit Protection**: 6-hour caching and conservative polling
- **State Synchronization**: Proper refresh triggers after operations
- **Enhanced Error Handling**: Better connection validation and error reporting

### Version 0.2.10
- **Configuration Flexibility**: Support for hostname, port, and full URL input
- **SSL/TLS Configuration**: Configurable SSL verification per instance
- **Configurable Rate Limiting**: User-adjustable cache duration, rate limits, and periods
- **Options Flow**: Runtime configuration changes without re-installation
- **Multi-Instance Support**: Different configurations per Portainer instance
- **Validation**: Comprehensive input validation with helpful error messages

## Roadmap

### Phase 2: Advanced Features & User Experience
- Docker Hub API integration for more accurate update detection
- Container health monitoring
- Resource usage alerts
- Backup and restore functionality
- Custom UI cards

### Phase 3: Advanced Automation & Integration
- Automated update strategies
- Integration with other Home Assistant components
- Advanced automation triggers
- Container dependency management

## Support

For issues and feature requests, please create an issue on the GitHub repository.

## License

This project is licensed under the MIT License.


