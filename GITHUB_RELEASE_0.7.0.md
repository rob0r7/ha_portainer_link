# HA Portainer Link 0.7.0

This release fixes several serious bugs found in a code review and on a real install. These include data loss on stack updates, broken logins after the Portainer session expires, and SSL verification that was silently turned off. It also blocks Portainer from updating itself, cleans up duplicate devices and gives the setup and options dialogs proper labels.

## ⚠️ Before you upgrade

- **Self-signed certificates:** If Portainer uses a self-signed certificate and **Verify SSL certificate** is on (the default), setup now fails with a clear hint. Earlier versions silently turned verification off on certificate errors. Open the integration options and turn **Verify SSL certificate** off.
- **Portainer self-updates are blocked:** Portainer and the Portainer agent can no longer be updated from Home Assistant. Recreating them through their own API stops Portainer partway through and leaves it down. Their update is still shown, but you need to apply it on the Docker host.

## Fixes

- **No more data loss on stack updates.** The stack update no longer stops and force-deletes containers with `v=1` before redeploying. That deleted anonymous volumes, for example database data without a named volume.
- **Stack update results are correct.** A successful update is no longer reported as "Stack Update Failed".
- **Username/password logins keep working.** The integration logs in again when the Portainer session expires (8 hours by default). Wrong credentials now fail setup with a clear error.
- **Update detection for official images.** Images such as `nginx:latest` or `postgres:16` are recognized again.
- **Update install actually updates.** The update entity now pulls the image and recreates the container (Portainer 2.19+). Image pulls run to completion and report errors.
- **SSL verification is honoured everywhere.** There is no longer a silent fallback to unverified connections.
- **Duplicate devices are removed.** Devices left over from older versions appeared next to the current ones with the same name and only unavailable entities. They are removed automatically on startup.
- **Disabled devices survive restarts.** Devices you disable in Home Assistant are no longer deleted on every restart ([#30](https://github.com/rob0r7/ha_portainer_link/issues/30), thanks @sjonez).
- **Stopped stacks can be started.** Stacks without running containers keep working **Start** buttons.

## Improvements

- **Less network traffic.** Each container is inspected only once per poll, and image metadata is cached. A typical poll makes about two Portainer requests per container instead of about six.
- **Readable dialogs.** Setup and options now have English and German labels, help texts and error messages. Intervals are entered in minutes, and the notification service can be picked from a list.
- **Update check interval works.** Values below 6 hours now take effect.
- **Diagnostics download.** **Download diagnostics** on the integration shows what it sees, with credentials redacted, to help with bug reports.

## Upgrade notes

Restart Home Assistant after upgrading. On first start the log shows how many legacy devices were removed, if any. Some entity IDs created next to the old duplicates keep their `_2` suffix. Rename them in Home Assistant if you like, and update any dashboards or automations that use them.
