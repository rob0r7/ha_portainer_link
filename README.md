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

---

## 🔧 Features

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


