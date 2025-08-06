import requests
import logging

_LOGGER = logging.getLogger(__name__)

class PortainerAPI:
    def __init__(self, host, username=None, password=None, api_key=None):
        self.host = host.rstrip("/")  # Host inkl. http:// oder https://
        self.username = username
        self.password = password
        self.api_key = api_key
        self.jwt = None
        self.headers = {}

        if api_key:
            _LOGGER.debug("Using API Key for Portainer auth")
            self.headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
        else:
            self.authenticate()

    def authenticate(self):
        """Authenticate using username/password to get JWT token."""
        url = f"{self.host}/api/auth"
        try:
            _LOGGER.debug("Authenticating with Portainer at %s", url)
            resp = requests.post(url, json={
                "Username": self.username,
                "Password": self.password
            }, timeout=10)
            resp.raise_for_status()
            self.jwt = resp.json()["jwt"]
            self.headers = {
                "Authorization": f"Bearer {self.jwt}",
                "Content-Type": "application/json"
            }
            _LOGGER.info("Successfully authenticated with Portainer")
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Portainer authentication failed: %s", e)
            raise

    def get_containers(self, endpoint_id):
        """Get list of containers from a specific endpoint."""
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        try:
            _LOGGER.debug("Requesting container list from %s", url)
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            containers = resp.json()
            _LOGGER.debug("Received %d containers", len(containers))
            for c in containers:
                _LOGGER.debug("→ %s", c.get("Names", ["<kein Name>"]))
            return containers
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Failed to get containers: %s", e)
            return []

    def restart_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/restart"
        try:
            _LOGGER.debug("Restarting container: %s", container_id)
            resp = requests.post(url, headers=self.headers, timeout=10)
            success = resp.status_code == 204
            _LOGGER.info("Restart container %s: %s", container_id, "OK" if success else f"FAILED ({resp.status_code})")
            return success
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Restart failed: %s", e)
            return False

    def start_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        try:
            _LOGGER.debug("Starting container: %s", container_id)
            resp = requests.post(url, headers=self.headers, timeout=10)
            success = resp.status_code == 204
            _LOGGER.info("Start container %s: %s", container_id, "OK" if success else f"FAILED ({resp.status_code})")
            return success
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Start failed: %s", e)
            return False

    def stop_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        try:
            _LOGGER.debug("Stopping container: %s", container_id)
            resp = requests.post(url, headers=self.headers, timeout=10)
            success = resp.status_code == 204
            _LOGGER.info("Stop container %s: %s", container_id, "OK" if success else f"FAILED ({resp.status_code})")
            return success
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Stop failed: %s", e)
            return False

    def inspect_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            _LOGGER.debug("Inspecting container: %s", container_id)
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Inspect failed: %s", e)
            return {}
