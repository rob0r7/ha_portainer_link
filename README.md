# 🐳 HA Portainer Link

Manage your Docker containers in Home Assistant, powered by Portainer!
**HA Portainer Link** is a [Home Assistant](https://www.home-assistant.io/) custom integration that connects one or more [Portainer](https://www.portainer.io/) instances and exposes your Docker containers as sensors, switches, and buttons in the Home Assistant UI.

> 🚀 Full restart control, resource monitoring, and multi-instance support – directly from your smart home dashboard.
> 
## 🚀 What is this?
HA Portainer Link is my very first official Home Assistant integration — born out of a simple dream:
To control, monitor, and love my Docker containers right from the Home Assistant dashboard.
No more SSH-ing, no more docker ps | grep, no more copy-pasting container IDs at 2 a.m.
Just pure, point-and-click magic — with restart buttons! 😎

<<<<<<< Updated upstream
---

## 🔧 Features
=======
- **Container Status Monitoring**: Real-time status, CPU, memory, and uptime sensors
- **Update Management**: Detect available updates and pull new images
- **Container Control**: Start, stop, and restart containers
- **Stack Management**: Manage Docker Compose stacks with dedicated controls (start, stop, force update)
- **Version Tracking**: Monitor current and available versions of container images
- **Multi-Instance Support**: Manage multiple Portainer instances from a single Home Assistant installation

### Stack Force Update
The integration now includes a "Stack Force Update" button that performs a complete stack update with:
- Force pulling of latest images from the registry
- Redeployment of all containers in the stack
- Cleanup of unused images (prune)
- Proper handling of Docker Compose stack lifecycle

This feature is particularly useful for stacks that need to be updated with the latest images without manual intervention.

## Installation
>>>>>>> Stashed changes

| Feature                     | Status |
|-----------------------------|--------|
| 🚦 Container status sensor   | ✅     |
| 🧠 CPU / RAM usage sensor    | ✅     |
| 🎯 Container image info      | ✅     |
| 🔄 Update available sensor   | ✅     |
| 📥 Pull update button        | ✅     |
| ⏯ Start/Stop/Restart button | ✅     |
| 🌐 Multiple Portainer hosts  | ✅     |
| 🛠 Configurable via UI       | ✅     |

---

## 😅 Why did I build this?
One day, I realized I had more containers than socks.
Sometimes I’d lose track of what was running where, and which port was open.
Home Assistant is my single source of truth, but Docker wasn’t talking to it.
So I made a bridge — and now, you can have it too.

---

## 📦 Installation

### Easiest: HACS

1. In Home Assistant, open **HACS → Integrations**
2. Click ⋮ → “Custom repositories”
3. Add: `https://github.com/rob0r7/ha_portainer_link` (Type: Integration)
4. Search for **Portainer Link**, install, restart HA

### Manual

1. Copy the `ha_portainer_link` directory to `/config/custom_components/`
2. Restart Home Assistant

## 🔧 Setup

<<<<<<< Updated upstream
1. Go to **Settings → Devices & Services → + Add Integration**
2. Search for “Portainer”
3. Enter your API URL, endpoint ID and API key (or user/pass)
4. 🎩 _Ta-dah!_ All your containers now in Home Assistant



---

## 📸 Screenshots

> <img width="2164" height="1110" alt="image" src="https://github.com/user-attachments/assets/8186ded7-919d-44e7-8a72-8ebc6aeca24e" />
<img width="2166" height="1116" alt="image" src="https://github.com/user-attachments/assets/548ba2df-a43a-49ae-9d15-3c173f344980" />
<img width="1011" height="760" alt="image" src="https://github.com/user-attachments/assets/b012baff-4171-4a61-9dad-48c17d0b3ff1" />
<img width="1135" height="897" alt="image" src="https://github.com/user-attachments/assets/72ea3151-051a-4792-bb4e-b0bbfe325f32" />
<img width="674" height="577" alt="image" src="https://github.com/user-attachments/assets/ba557c3b-3d1d-4cb0-83c4-f49b94c1d6f1" />
<img width="1054" height="914" alt="image" src="https://github.com/user-attachments/assets/3a83ec19-b9ce-4946-938a-790e84380dfe" />

---



## ⚙️ Requirements

- Home Assistant 2023.6 or newer
- Portainer API (v2+)
- API key **or** user/password for Portainer

## 🛣️ Roadmap

- [ ] More sensors (disk/network)
- [ ] Service call: Pull image / recreate
- [ ] Docker stack support
- [ ] Option to auto-create a dashboard for all containers
- [ ] HACS default store (maybe!)

---

## 👋 Contribute

This is my first *official* HA integration.  
Found a bug? [Open an issue!](https://github.com/rob0r7/ha_portainer_link/issues)  
Want a new feature? PRs welcome!  
Or just say hi and share what you build. ⭐️

---

## 📜 License

MIT

---

_This project was made with:  
☕️ + 💡 + 😴 - sleep + ❤️ for Home Assistant & Docker._

## .. just kidding, I confess:
I admit it – I didn’t code this all by myself. Almost every line was the result of long conversations with AI, lots of copy-paste, and me occasionally screaming at my screen. My only true contribution? Endless chats with artificial intelligence and the patience to deal with its quirks.
So please: have mercy if your feature requests take time, or don’t land exactly how you imagined! If you still feel like buying me a coffee, you’re welcome to do so – it helps keep the AI arguments development going. ☕️😉

<a href="https://www.buymeacoffee.com/bobimneuland" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

Enjoy, fellow automation nerds!

---
=======
### Required Settings
- **Host**: Your Portainer instance URL (e.g., `http://192.168.1.100:9000`)
- **Endpoint ID**: The Docker endpoint ID in Portainer (usually `1` for local Docker)
- **Authentication**: Either username/password or API key

### Optional Settings
- **API Key**: Alternative to username/password authentication

## Troubleshooting

### Duplicate Stack Devices
If you see duplicate stack devices (e.g., "Stack: wekan (192.168.0.105)" appearing twice), this usually indicates you have multiple configuration entries for the same Portainer instance.

**Solution:**
1. Go to **Settings** → **Devices & Services**
2. Look for multiple "HA Portainer Link" entries
3. Remove the duplicate configuration entries, keeping only one per Portainer instance
4. Restart Home Assistant

### Containers Appearing as Standalone When They Should Be in Stacks
If containers that are part of a Docker Compose stack are appearing as standalone devices instead of being grouped under a stack device, this indicates a stack detection issue.

**Diagnosis:**
1. Enable debug logging for the integration:
   ```yaml
   logger:
     custom_components.ha_portainer_link: debug
   ```
2. Check the Home Assistant logs for stack detection messages
3. Look for messages like:
   - `🔍 Stack detection for container: stack_name=...`
   - `✅ Container is part of stack: ...`
   - `ℹ️ Container is standalone (no stack labels found)`

**Common Causes:**
- Container inspection API calls failing
- Missing Docker Compose labels
- Network connectivity issues to Portainer

**Solution:**
1. Verify Portainer API connectivity
2. Check that containers are properly deployed via Docker Compose
3. Ensure the `com.docker.compose.project` label is present on stack containers


To enable detailed logging, add to your `configuration.yaml`:
```yaml
logger:
  custom_components.ha_portainer_link: debug
```

## Roadmap

- [ ] Additional sensors (disk usage, network statistics)
- [ ] Service calls for container management
- [ ] Auto dashboard creation
- [ ] HACS default store integration

## Recent Updates

### Version 0.2.5
- ✅ **Fixed Stack Update API Endpoint**: Corrected the API endpoint from `/api/stacks/{id}/update` to `/api/stacks/{id}?endpointId={id}&type=2`
- ✅ **Added Type Parameter**: Added `type=2` parameter for Docker Compose stacks in the update request
- ✅ **Enhanced Stack Environment Variables**: Added support for environment variables in stack updates (UID, GID, etc.)
- ✅ **Improved Stack Details Retrieval**: Enhanced stack update to fetch actual environment variables from Portainer
- ✅ **Better Default Environment Handling**: Added fallback to default UID/GID values when environment variables are not found
- ✅ **Enhanced Debug Logging**: Added detailed logging for environment variables and payload structure

### Version 0.2.4

### Version 0.2.3
- ✅ **Enhanced Stack Force Update Logging**: Added comprehensive debug logging for all API calls and responses
- ✅ **Improved Stack Matching**: Enhanced stack search to match both name and endpoint ID for accuracy
- ✅ **Better Error Handling**: Added detailed error messages with HTTP status codes and response text
- ✅ **Stack File Content Validation**: Added validation and preview of stack file content before update

### Version 0.2.2
- ✅ **Fixed Stack Force Update API**: Corrected to use proper Portainer API endpoints (`/api/stacks/{id}/update?endpointId={id}`)
- ✅ **Fixed Request Payload**: Updated to use correct field names (`PullImage`, `Prune`) and removed invalid `endpointId` from body
- ✅ **Fixed Stack File Retrieval**: Corrected endpoint to `/api/stacks/{id}/file`
- ✅ **Enhanced Stack Filtering**: Properly filter stacks by endpoint ID

### Version 0.2.1
- ✅ **Fixed Stack Force Update**: Corrected API endpoints to use endpoint-specific URLs
- ✅ **Enhanced Stack API Calls**: Updated all stack operations to use `/api/endpoints/{endpoint_id}/stacks/` endpoints
- ✅ **Improved Error Handling**: Better debugging information for stack update failures

### Version 0.2.0
- ✅ **Update Available Sensor**: Detect if a new image version is available for containers
- ✅ **Pull Update Button**: Pull newer images and recreate/update containers with config persistence
- ✅ **Version Sensors**: Display current and available image versions
- ✅ **Container Control**: Start, stop, and restart individual containers
- ✅ **Stack Management**: Group containers belonging to Docker Compose stacks under single devices
- ✅ **Stack Force Update**: Complete stack updates with image pulling and redeployment
- ✅ **Multi-Portainer Support**: Unique device and entity identification across multiple instances
- ✅ **Enhanced Error Handling**: Comprehensive logging and user feedback for all operations
- ✅ **Device Organization**: Proper grouping of stack vs standalone containers
- ✅ **Debug Logging**: Detailed troubleshooting information for API calls and operations

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/rob0r7/ha_portainer_link).
>>>>>>> Stashed changes


