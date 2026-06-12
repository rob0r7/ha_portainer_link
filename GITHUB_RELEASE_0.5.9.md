# Release Title
v0.5.9 - Dashboard Functionality Removal

---

# Release Notes

## 🚨 Breaking Changes

This release removes the automatic Lovelace dashboard creation functionality that was introduced in v0.5.0.

### Removed Features
- Automatic dashboard creation during integration setup
- `ha_portainer_link.create_dashboard` service
- `ha_portainer_link.diagnose_dashboard` service
- Dashboard configuration options in config flow

## ✨ Changes

### Simplified Setup
- Config flow now directly creates entry after basic configuration (no dashboard step)
- Faster and more straightforward setup experience

### Code Improvements
- Removed ~350+ lines of dashboard-related code
- Eliminated dependency on Lovelace API
- Reduced complexity and potential failure points
- Cleaner, more maintainable codebase

## 📝 Migration Notes

**For existing users:**
- Your existing dashboard will remain untouched (no data loss)
- All entities, sensors, and controls remain fully functional
- To recreate/modify dashboards, use Home Assistant's built-in Lovelace UI

**For new users:**
- Setup is now simpler - no dashboard configuration step
- Create custom dashboards manually using Home Assistant's dashboard editor

## ✅ Core Functionality Unchanged

All container and stack management features continue to work:
- Container management (start, stop, restart)
- Stack management (start, stop, update)
- Real-time monitoring (status, CPU, memory, uptime)
- Update availability sensors
- Version tracking
- All sensors, switches, and buttons

## 🔗 Full Details

See [CHANGELOG.md](CHANGELOG.md) for complete change history.

