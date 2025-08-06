# 🐳 HA Portainer Link

**HA Portainer Link** is a [Home Assistant](https://www.home-assistant.io/) custom integration that connects one or more [Portainer](https://www.portainer.io/) instances and exposes your Docker containers as sensors, switches, and buttons in the Home Assistant UI.

> 🚀 Full restart control, resource monitoring, and multi-instance support – directly from your smart home dashboard.

---

## 🔧 Features

| Feature                     | Status |
|-----------------------------|--------|
| 🚦 Container status sensor   | ✅     |
| 🧠 CPU / RAM usage sensor    | ✅     |
| 🔁 Uptime tracking           | ✅     |
| 🎯 Container image info      | ✅     |
| ⏯ Start/Stop/Restart button | ✅     |
| 🌐 Multiple Portainer hosts  | ✅     |
| 🔍 Container filtering       | 🔜     |
| 🛠 Configurable via UI       | ✅     |

---

## 📸 Screenshots

> _(Coming soon: UI screenshots of container sensors & controls)_

---

## 🚀 Installation

1. Clone the repository or download the ZIP:

```bash
git clone https://github.com/YOUR_USERNAME/ha_portainer_link.git
Copy the folder:

bash
Kopieren
Bearbeiten
mv ha_portainer_link/custom_components/ha_portainer_link \
   /config/custom_components/ha_portainer_link
Restart Home Assistant.

Go to Settings → Devices & Services → Add Integration and search for Portainer.

⚙️ Configuration
Everything is done via the Home Assistant UI:

Portainer URL (http:// or https://)

API Key (created in Portainer UI)

Endpoint ID (from Portainer instance)

No YAML needed. Changes can be edited later via the UI as well.

📡 Sensors Created
Each container will automatically expose:

container_name_status – Running / Paused / Stopped

container_name_cpu – % CPU usage

container_name_memory – MB RAM usage

container_name_uptime – Time since last restart

container_name_image – The Docker image used

And control:

container_name_switch – Start / Stop

container_name_restart – Restart button

🧠 Roadmap
 Container filtering by name/label

 Lock support (volume/filesystem)

 Real-time updates (WebSocket)

 Snapshot backup triggers

 Theme / UI custom widgets

🧪 Development
You're welcome to contribute! Open an issue, PR, or feature suggestion.

Local development:

bash
hass --script check_config
📄 License
This project is licensed under the MIT License.

💬 Credits
Built with ❤️ for Home Assistant and Docker fans by rob0r7.

Inspired by portainer, hass.io, and the power of custom integrations.


---


…you’ll have a great foundation for your public project!

Want me to generate this as a file now for upload?
