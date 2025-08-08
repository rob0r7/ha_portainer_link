DOMAIN = "ha_portainer_link"

# Basic Configuration
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_API_KEY = "api_key"
CONF_ENDPOINT_ID = "endpoint_id"

# Integration Mode Configuration
CONF_INTEGRATION_MODE = "integration_mode"

# Default Values
DEFAULT_UPDATE_INTERVAL = 5  # minutes

# Integration Modes
INTEGRATION_MODE_LIGHTWEIGHT = "lightweight"
INTEGRATION_MODE_FULL = "full"

# Mode Presets
INTEGRATION_MODE_PRESETS = {
    INTEGRATION_MODE_LIGHTWEIGHT: {
        "description": "Lightweight View - Basic container control only",
        "features": {
            "enable_stack_view": False,
            "enable_resource_sensors": False,
            "enable_version_sensors": False,
            "enable_update_sensors": False,
            "enable_stack_buttons": False,
            "enable_container_buttons": True,
            "update_interval": 10,  # Less frequent updates
        }
    },
    INTEGRATION_MODE_FULL: {
        "description": "Full View - Complete functionality with all features",
        "features": {
            "enable_stack_view": True,
            "enable_resource_sensors": True,
            "enable_version_sensors": True,
            "enable_update_sensors": True,
            "enable_stack_buttons": True,
            "enable_container_buttons": True,
            "update_interval": 5,  # More frequent updates
        }
    }
}
