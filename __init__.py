from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY, CONF_ENDPOINT_ID
from .portainer_api import PortainerAPI

async def async_setup(hass, config):
    """Set up HA Portainer Link from configuration.yaml."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    host = conf[CONF_HOST]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    api_key = conf.get(CONF_API_KEY)
    endpoint_id = conf[CONF_ENDPOINT_ID]

    api = PortainerAPI(host, username, password, api_key)
    containers = api.get_containers(endpoint_id)

    for container in containers:
        hass.states.async_set(
            f"{DOMAIN}.{container['Names'][0].strip('/')}",
            container["State"]
        )

    return True
