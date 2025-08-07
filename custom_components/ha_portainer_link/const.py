DOMAIN = "ha_portainer_link"

# Basic Configuration
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_API_KEY = "api_key"
CONF_ENDPOINT_ID = "endpoint_id"

# Advanced Configuration
CONF_PORT = "port"
CONF_SSL_VERIFY = "ssl_verify"
CONF_TIMEOUT = "timeout"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_CACHE_DURATION = "cache_duration"
CONF_RATE_LIMIT_CHECKS = "rate_limit_checks"
CONF_RATE_LIMIT_PERIOD = "rate_limit_period"
CONF_ENABLE_UPDATE_CHECKS = "enable_update_checks"
CONF_ENABLE_HEALTH_MONITORING = "enable_health_monitoring"
CONF_ENABLE_RESOURCE_MONITORING = "enable_resource_monitoring"

# Integration Mode Configuration
CONF_INTEGRATION_MODE = "integration_mode"
CONF_ENABLE_STACK_VIEW = "enable_stack_view"
CONF_ENABLE_CONTAINER_LOGS = "enable_container_logs"
CONF_ENABLE_RESOURCE_SENSORS = "enable_resource_sensors"
CONF_ENABLE_VERSION_SENSORS = "enable_version_sensors"
CONF_ENABLE_UPDATE_SENSORS = "enable_update_sensors"
CONF_ENABLE_STACK_BUTTONS = "enable_stack_buttons"
CONF_ENABLE_CONTAINER_BUTTONS = "enable_container_buttons"
CONF_ENABLE_BULK_OPERATIONS = "enable_bulk_operations"

# Default Values
DEFAULT_PORT = 9000
DEFAULT_SSL_VERIFY = True
DEFAULT_TIMEOUT = 30
DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_CACHE_DURATION = 6  # hours
DEFAULT_RATE_LIMIT_CHECKS = 50
DEFAULT_RATE_LIMIT_PERIOD = 6  # hours
DEFAULT_ENABLE_UPDATE_CHECKS = True
DEFAULT_ENABLE_HEALTH_MONITORING = True
DEFAULT_ENABLE_RESOURCE_MONITORING = True

# Integration Mode Defaults
DEFAULT_INTEGRATION_MODE = "full"
DEFAULT_ENABLE_STACK_VIEW = True
DEFAULT_ENABLE_CONTAINER_LOGS = False
DEFAULT_ENABLE_RESOURCE_SENSORS = True
DEFAULT_ENABLE_VERSION_SENSORS = True
DEFAULT_ENABLE_UPDATE_SENSORS = True
DEFAULT_ENABLE_STACK_BUTTONS = True
DEFAULT_ENABLE_CONTAINER_BUTTONS = True
DEFAULT_ENABLE_BULK_OPERATIONS = False

# Validation
MIN_UPDATE_INTERVAL = 1  # minutes
MAX_UPDATE_INTERVAL = 60  # minutes
MIN_CACHE_DURATION = 1  # hours
MAX_CACHE_DURATION = 24  # hours
MIN_RATE_LIMIT_CHECKS = 10
MAX_RATE_LIMIT_CHECKS = 100

# Integration Modes
INTEGRATION_MODE_LIGHTWEIGHT = "lightweight"
INTEGRATION_MODE_STANDARD = "standard"
INTEGRATION_MODE_FULL = "full"
INTEGRATION_MODE_CUSTOM = "custom"

# Mode Presets
INTEGRATION_MODE_PRESETS = {
    INTEGRATION_MODE_LIGHTWEIGHT: {
        "description": "Minimal functionality - basic container control only",
        "features": {
            CONF_ENABLE_STACK_VIEW: False,
            CONF_ENABLE_CONTAINER_LOGS: False,
            CONF_ENABLE_RESOURCE_SENSORS: False,
            CONF_ENABLE_VERSION_SENSORS: False,
            CONF_ENABLE_UPDATE_SENSORS: False,
            CONF_ENABLE_STACK_BUTTONS: False,
            CONF_ENABLE_CONTAINER_BUTTONS: True,
            CONF_ENABLE_BULK_OPERATIONS: False,
            CONF_UPDATE_INTERVAL: 10,  # Less frequent updates
            CONF_ENABLE_HEALTH_MONITORING: False,
            CONF_ENABLE_RESOURCE_MONITORING: False,
        }
    },
    INTEGRATION_MODE_STANDARD: {
        "description": "Balanced functionality - most common features",
        "features": {
            CONF_ENABLE_STACK_VIEW: True,
            CONF_ENABLE_CONTAINER_LOGS: False,
            CONF_ENABLE_RESOURCE_SENSORS: True,
            CONF_ENABLE_VERSION_SENSORS: True,
            CONF_ENABLE_UPDATE_SENSORS: True,
            CONF_ENABLE_STACK_BUTTONS: True,
            CONF_ENABLE_CONTAINER_BUTTONS: True,
            CONF_ENABLE_BULK_OPERATIONS: False,
            CONF_UPDATE_INTERVAL: 5,
            CONF_ENABLE_HEALTH_MONITORING: True,
            CONF_ENABLE_RESOURCE_MONITORING: True,
        }
    },
    INTEGRATION_MODE_FULL: {
        "description": "Complete functionality - all features enabled",
        "features": {
            CONF_ENABLE_STACK_VIEW: True,
            CONF_ENABLE_CONTAINER_LOGS: True,
            CONF_ENABLE_RESOURCE_SENSORS: True,
            CONF_ENABLE_VERSION_SENSORS: True,
            CONF_ENABLE_UPDATE_SENSORS: True,
            CONF_ENABLE_STACK_BUTTONS: True,
            CONF_ENABLE_CONTAINER_BUTTONS: True,
            CONF_ENABLE_BULK_OPERATIONS: True,
            CONF_UPDATE_INTERVAL: 3,  # More frequent updates
            CONF_ENABLE_HEALTH_MONITORING: True,
            CONF_ENABLE_RESOURCE_MONITORING: True,
        }
    }
}
