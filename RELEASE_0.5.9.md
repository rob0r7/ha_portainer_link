# Release v0.5.9 - Dashboard Functionality Removal

**Release Date:** December 7, 2025

## 📋 Overview

This release removes the automatic Lovelace dashboard creation functionality that was introduced in v0.5.0. This change simplifies the integration and reduces complexity, focusing the integration on its core container and stack management capabilities.

## 🚨 Breaking Changes

### Removed Features

- **Automatic Dashboard Creation**: The integration no longer automatically creates a Lovelace dashboard during setup
- **Dashboard Services**: The following services have been removed:
  - `ha_portainer_link.create_dashboard` - Manual dashboard creation service
  - `ha_portainer_link.diagnose_dashboard` - Dashboard diagnostic service
- **Config Flow Dashboard Options**: Dashboard configuration options (title, URL path, enable/disable) have been removed from the setup flow

## 🔄 What Changed

### Simplified Setup Process
- Config flow now directly creates the integration entry after basic configuration
- Removed the dashboard configuration step from the setup wizard
- Faster and more straightforward setup experience

### Code Simplification
- Removed all dashboard-related code (~350+ lines)
- Eliminated dependency on Lovelace API
- Reduced integration complexity and potential failure points
- Cleaner codebase focused on core functionality

### Dependency Changes
- Removed `after_dependencies: ["lovelace"]` from manifest.json
- No longer requires Lovelace to be loaded before integration setup

## 📝 Migration Notes

### For Existing Users

**If you had automatic dashboard creation enabled:**
- Your existing dashboard will remain untouched - it won't be automatically deleted
- If you want to recreate or modify the dashboard, you'll need to do so manually through Home Assistant's Lovelace UI
- No data loss - all entities, sensors, and controls remain fully functional

**If you used the dashboard services:**
- The `create_dashboard` and `diagnose_dashboard` services are no longer available
- You can manually create dashboards through Home Assistant's dashboard editor if needed

### For New Users
- Setup is now simpler - no dashboard configuration step
- All container management features remain fully functional
- You can create custom dashboards manually using Home Assistant's built-in tools

## ✅ What Still Works

All core functionality remains unchanged:
- ✅ Container management (start, stop, restart)
- ✅ Stack management (start, stop, update)
- ✅ Real-time monitoring (status, CPU, memory, uptime)
- ✅ Update availability sensors
- ✅ Version tracking
- ✅ All sensors, switches, and buttons
- ✅ Automatic container discovery
- ✅ SSL support with automatic fallback

## 🎯 Why This Change?

The dashboard creation functionality proved to be:
- **Unreliable**: Frequent issues with Home Assistant's internal Lovelace API across different versions
- **Complex**: Required extensive workarounds and compatibility code for different HA versions
- **Unnecessary**: Users can easily create custom dashboards using Home Assistant's built-in tools
- **Maintenance burden**: Constant updates needed to keep pace with Home Assistant API changes

This removal allows the integration to focus on what it does best: providing reliable container and stack management through Portainer.

## 📦 Installation

### Upgrade from Previous Versions
1. Update through HACS or manual installation
2. Restart Home Assistant
3. No configuration changes needed - your existing setup will continue to work

### Fresh Installation
Follow the standard installation process - the setup flow is now simpler without dashboard configuration.

## 🔗 Links

- [Full Changelog](CHANGELOG.md)
- [Documentation](README.md)
- [GitHub Repository](https://github.com/rob0r7/ha_portainer_link)

## 🙏 Feedback

If you have questions or concerns about this change, please open an issue on GitHub. We appreciate your understanding as we work to make the integration more reliable and maintainable.

