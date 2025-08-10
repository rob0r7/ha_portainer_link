# file: custom_components/ha_portainer_link/stack_api.py

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple

import aiohttp
from aiohttp.client_exceptions import ClientConnectorCertificateError

_LOGGER = logging.getLogger(__name__)


class PortainerStackAPI:
    """Handle Portainer stack operations including force-redeploy with fresh images."""

    def __init__(self, base_url: str, auth, ssl_verify: bool = True, session=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth  # expects .session (aiohttp.ClientSession) and .get_headers()
        self.ssl_verify = ssl_verify
        self.session = session  # Use shared session from main API

    # ---------------------------
    # Small request helper
    # ---------------------------
    async def _request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Centralized request to toggle SSL on cert errors (reduces repetitive try/except).
        Why: Portainer CE on LAN often uses self‑signed certs; we fail open by retrying with ssl=False.
        """
        headers = kwargs.pop("headers", None) or self.auth.get_headers()
        ssl = kwargs.pop("ssl", self.ssl_verify)
        session = self.session or self.auth.session

        try:
            resp = await session.request(method, url, headers=headers, ssl=ssl, **kwargs)
            return resp
        except ClientConnectorCertificateError as e:
            _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
            # Persist choice to avoid future failures.
            self.ssl_verify = False
            resp = await session.request(method, url, headers=headers, ssl=False, **kwargs)
            return resp

    # ---------------------------
    # Read helpers
    # ---------------------------
    async def _get_stack_by_name(self, endpoint_id: int, stack_name: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/stacks"
        async with await self._request("GET", url) as resp:
            if resp.status != 200:
                _LOGGER.error("❌ Could not list stacks: HTTP %s", resp.status)
                return None
            stacks: List[Dict[str, Any]] = await resp.json()
            for st in stacks:
                if st.get("EndpointId") == endpoint_id and st.get("Name") == stack_name:
                    return st
        return None

    async def _get_stack_detail(self, stack_id: int) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/stacks/{stack_id}"
        async with await self._request("GET", url) as resp:
            if resp.status != 200:
                _LOGGER.error("❌ Could not fetch stack %s details: HTTP %s", stack_id, resp.status)
                return None
            return await resp.json()

    async def _list_stack_container_ids(self, endpoint_id: int, stack_name: str) -> List[str]:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        async with await self._request("GET", url) as resp:
            if resp.status != 200:
                _LOGGER.error("❌ Could not list containers: HTTP %s", resp.status)
                return []
            data: List[Dict[str, Any]] = await resp.json()
            ids: List[str] = []
            for c in data:
                # Portainer/Docker compose labels
                labels = c.get("Labels", {}) or {}
                if labels.get("com.docker.compose.project") == stack_name:
                    ids.append(c.get("Id"))
            return ids

    # ---------------------------
    # Public list/start/stop
    # ---------------------------
    async def get_stacks(self, endpoint_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/stacks"
        async with await self._request("GET", url) as resp:
            if resp.status != 200:
                _LOGGER.error("❌ Could not get stacks list: HTTP %s", resp.status)
                return []
            stacks = await resp.json()
            return [s for s in stacks if s.get("EndpointId") == endpoint_id]

    async def stop_stack(self, endpoint_id: int, stack_name: str) -> bool:
        ids = await self._list_stack_container_ids(endpoint_id, stack_name)
        if not ids:
            _LOGGER.info("ℹ️ No containers found for stack %s (may be fresh stack)", stack_name)
            return True  # Consider this success for fresh stacks
        ok = 0
        for cid in ids:
            url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{cid}/stop"
            async with await self._request("POST", url) as resp:
                if resp.status == 204:
                    ok += 1
                else:
                    _LOGGER.warning("⚠️ Failed to stop %s: HTTP %s", cid, resp.status)
        _LOGGER.info("🛑 Stopped %d/%d containers in stack %s", ok, len(ids), stack_name)
        return ok == len(ids)

    async def start_stack(self, endpoint_id: int, stack_name: str) -> bool:
        stack = await self._get_stack_by_name(endpoint_id, stack_name)
        if not stack:
            _LOGGER.error("❌ Stack %s not found on endpoint %s", stack_name, endpoint_id)
            return False
        stack_id = stack.get("Id")
        url = f"{self.base_url}/api/stacks/{stack_id}/start?endpointId={endpoint_id}"
        _LOGGER.debug("🔍 Starting stack %s with URL: %s", stack_name, url)
        async with await self._request("POST", url) as resp:
            if resp.status == 200:
                _LOGGER.info("▶️ Started stack %s", stack_name)
                return True
            else:
                # Try to get error details
                try:
                    error_body = await resp.text()
                    _LOGGER.error("❌ Failed to start stack %s: HTTP %s - %s", stack_name, resp.status, error_body)
                except Exception:
                    _LOGGER.error("❌ Failed to start stack %s: HTTP %s", stack_name, resp.status)
                return False

    # ---------------------------
    # Force update with fresh images (stop → delete → PUT update → wait)
    # ---------------------------
    async def update_stack(
        self,
        endpoint_id: int,
        stack_name: str,
        *,
        pull_image: bool = True,
        prune: bool = False,
        wait_timeout: float = 90.0,
        wait_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Force-redeploy a stack with fresh images and current compose settings.

        Returns a dict with step results.
        """
        _LOGGER.info("🔄 Starting comprehensive update for stack %s", stack_name)
        
        result: Dict[str, Any] = {
            "stack": stack_name,
            "stopped": False,
            "deleted": [],
            "update_put": None,
            "started": False,
            "wait_ready": False,
            "compose_retrieved": False,
        }

        # Resolve stack + compose content/env
        stack = await self._get_stack_by_name(endpoint_id, stack_name)
        if not stack:
            _LOGGER.error("❌ Stack %s not found on endpoint %s", stack_name, endpoint_id)
            return result
        stack_id = stack.get("Id")
        _LOGGER.debug("🔍 Found stack %s with ID %s", stack_name, stack_id)

        detail = await self._get_stack_detail(stack_id)
        if not detail:
            _LOGGER.error("❌ Could not get stack detail for %s (ID: %s)", stack_name, stack_id)
            return result

        _LOGGER.debug("🔍 Stack detail keys: %s", list(detail.keys()) if detail else "None")

        # Try multiple sources for compose content
        compose = ""
        env = []
        
        # Try detail first
        if detail:
            compose = detail.get("StackFileContent", "").strip()
            env = detail.get("Env", [])
            _LOGGER.debug("🔍 From detail - compose length: %d, env count: %d", len(compose), len(env))
        
        # If detail doesn't have content, try the stack list item
        if not compose and stack:
            compose = stack.get("StackFileContent", "").strip()
            if not env:
                env = stack.get("Env", [])
            _LOGGER.debug("🔍 From stack list - compose length: %d, env count: %d", len(compose), len(env))
        
        # If still no compose content, try to get it from the stack file endpoint
        if not compose:
            _LOGGER.info("🔄 Trying to get compose content from stack file endpoint for %s", stack_name)
            try:
                file_url = f"{self.base_url}/api/stacks/{stack_id}/file?endpointId={endpoint_id}"
                async with await self._request("GET", file_url) as resp:
                    if resp.status == 200:
                        file_data = await resp.json()
                        compose = file_data.get("StackFileContent", "").strip()
                        _LOGGER.debug("🔍 From file endpoint - compose length: %d", len(compose))
                    else:
                        _LOGGER.warning("⚠️ Could not get stack file: HTTP %s", resp.status)
            except Exception as e:
                _LOGGER.warning("⚠️ Error getting stack file: %s", e)
        
        if len(compose) < 10:
            _LOGGER.error("❌ Stack compose content invalid/empty for %s (length: %d)", stack_name, len(compose))
            _LOGGER.error("❌ Available stack data keys: %s", list(stack.keys()) if stack else "None")
            _LOGGER.error("❌ Available detail keys: %s", list(detail.keys()) if detail else "None")
            result["compose_retrieved"] = False
            # Try to start the stack anyway as a fallback
            _LOGGER.info("🔄 Trying to start stack %s as fallback", stack_name)
            started = await self.start_stack(endpoint_id, stack_name)
            result["started"] = started
            if started:
                # Wait for containers to be running
                ready = await self._wait_until_running(endpoint_id, stack_name, timeout=wait_timeout, interval=wait_interval)
                result["wait_ready"] = ready
            return result
        else:
            result["compose_retrieved"] = True
            _LOGGER.info("✅ Successfully retrieved compose content for %s (length: %d)", stack_name, len(compose))

        # Stop containers (best effort)
        await self.stop_stack(endpoint_id, stack_name)
        result["stopped"] = True

        # Delete existing containers to force recreation
        deleted: List[str] = []
        ids = await self._list_stack_container_ids(endpoint_id, stack_name)
        _LOGGER.info("🔄 Deleting %d containers for stack %s", len(ids), stack_name)
        for cid in ids:
            url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{cid}?force=1&v=1"
            async with await self._request("DELETE", url) as resp:
                if resp.status in (204, 200, 404):  # 404 means already gone
                    deleted.append(cid)
                    _LOGGER.debug("✅ Deleted container %s", cid)
                else:
                    _LOGGER.warning("⚠️ Failed to delete %s: HTTP %s", cid, resp.status)
        result["deleted"] = deleted
        _LOGGER.info("✅ Deleted %d/%d containers for stack %s", len(deleted), len(ids), stack_name)

        # PUT update (pull fresh images + redeploy)
        put_url = f"{self.base_url}/api/stacks/{stack_id}?endpointId={endpoint_id}"
        payload = {
            "prune": prune,
            "pullImage": pull_image,
            "env": env,
            "stackFileContent": compose,
        }
        _LOGGER.debug("🔍 Updating stack %s with URL: %s", stack_name, put_url)
        _LOGGER.debug("🔍 Update payload keys: %s", list(payload.keys()))
        async with await self._request("PUT", put_url, json=payload) as resp:
            ok = resp.status == 200
            body = None
            try:
                body = await resp.text()
            except Exception:  # noqa: BLE001
                pass
            result["update_put"] = {"ok": ok, "status": resp.status, "body": body}
            if not ok:
                _LOGGER.error("❌ Stack update PUT failed: HTTP %s %s", resp.status, body)
                # Try fallback start API.
                _LOGGER.info("🔄 Trying fallback start for stack %s", stack_name)
                started = await self.start_stack(endpoint_id, stack_name)
                result["started"] = started
                if not started:
                    _LOGGER.error("❌ Fallback start also failed for stack %s", stack_name)
                    # Try one more time with a delay
                    _LOGGER.info("🔄 Trying one more time with delay for stack %s", stack_name)
                    import asyncio
                    await asyncio.sleep(5)
                    started = await self.start_stack(endpoint_id, stack_name)
                    result["started"] = started
                    if not started:
                        _LOGGER.error("❌ All attempts to start stack %s failed", stack_name)
                        return result
            else:
                _LOGGER.info("✅ Stack update PUT successful for %s", stack_name)

        # After successful PUT (or fallback start), wait for containers to be healthy/running
        _LOGGER.info("🔄 Waiting for stack %s containers to be running...", stack_name)
        ready = await self._wait_until_running(endpoint_id, stack_name, timeout=wait_timeout, interval=wait_interval)
        result["wait_ready"] = ready
        
        if ready:
            _LOGGER.info("✅ Stack %s update completed successfully", stack_name)
        else:
            _LOGGER.warning("⚠️ Stack %s update completed but containers may not be fully ready", stack_name)
        
        _LOGGER.info("✅ Stack %s update completed: %s", stack_name, result)
        return result

    # ---------------------------
    # Wait helpers
    # ---------------------------
    async def _wait_until_running(self, endpoint_id: int, stack_name: str, *, timeout: float, interval: float) -> bool:
        """Wait until all containers for the stack are running, time bounded.
        Uses two lists: expected containers (all=1) filtered by stack label, and running (all=0).
        Success requires expected_count > 0 and running_count == expected_count.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            # Determine expected containers for this stack
            expected_ids = await self._list_stack_container_ids(endpoint_id, stack_name)
            if not expected_ids:
                await asyncio.sleep(interval)
                continue

            # Get currently running containers and count how many belong to the stack
            running_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=0"
            async with await self._request("GET", running_url) as resp:
                if resp.status != 200:
                    await asyncio.sleep(interval)
                    continue
                running_data: List[Dict[str, Any]] = await resp.json()
                running_count = 0
                for c in running_data:
                    labels = c.get("Labels", {}) or {}
                    if labels.get("com.docker.compose.project") == stack_name:
                        running_count += 1
                if running_count == len(expected_ids) and running_count > 0:
                    return True

            await asyncio.sleep(interval)
        return False
