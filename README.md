# HA Portainer Link

A custom integration for [Home Assistant](https://www.home-assistant.io/) that connects to one or more [Portainer](https://www.portainer.io/) instances and provides:

- Container state sensors (running, paused, stopped)
- CPU, RAM, image, uptime sensors
- Start/Stop/Restart switches and buttons
- Full support for multiple Portainer endpoints
- Configurable via Home Assistant UI

---

## 🔧 Installation

1. Clone this repository into your Home Assistant config folder:

```bash
git clone https://github.com/YOURUSERNAME/ha_portainer_link.git

2. Move the custom_components/ha_portainer_link folder into your /config/custom_components/.

3. Restart Home Assistant.

4. Go to Settings → Devices & Services → Add Integration and search for Portainer.


🧠 Configuration Options
Via UI:

Portainer URL (http or https)
API Key
Endpoint ID

| Feature              | Status |
| -------------------- | ------ |
| CPU / RAM Monitoring | ✅      |
| Restart Button       | ✅      |
| Uptime Sensor        | ✅      |
| Filter Container     | 🔜     |
| Options Flow         | 🔜     |


💡 Planned
Lock support (locks inside containers)

Filter UI

Websocket-based status updates (faster)

Snapshot support?
