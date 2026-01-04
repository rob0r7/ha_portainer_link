# Enhancements Since v0.4.0

## Version 0.4.0 (2025-08-08)

### Stack Update Functionality
- ✅ **Comprehensive stack update functionality** with multi-step process
- ✅ **Image pulling for all containers** in a stack before update
- ✅ **Container recreation** with proper cleanup and redeployment
- ✅ **Robust error handling and fallback mechanisms** for stack operations
- ✅ **Button state management** during stack updates
- ✅ **Enhanced logging and progress tracking** for stack operations

### DNS Query Optimization
- ✅ **Comprehensive session sharing** across all API modules
- ✅ **Connection pooling and session reuse** to reduce DNS lookups (addresses GitHub issue #19)

---

## Version 0.5.0 (2025-11-25) ⚠️ *Removed in 0.5.9*

### Dashboard Features (Removed)
- ⚠️ Automatic Lovelace dashboard creation with organized views
- ⚠️ Dashboard service `ha_portainer_link.create_dashboard` for manual dashboard creation
- ⚠️ Automatic dashboard generation during integration setup
- ⚠️ Home view with global container update overview
- ⚠️ Stack-specific views with container controls and status
- ⚠️ Standalone container view for non-stack containers
- ⚠️ Configurable dashboard title and URL path during setup
- ⚠️ Delayed dashboard rebuild to include all entities after initial load
- ⚠️ Dashboard configuration options in config flow

*Note: These features were removed in v0.5.9 due to reliability issues with Home Assistant's Lovelace API across different versions.*

---

## Version 0.5.9 (2025-12-07)

### Code Quality Improvements
- ✅ **Simplified integration setup** - removed dashboard creation step
- ✅ **Reduced codebase complexity** - removed ~350+ lines of dashboard-related code
- ✅ **Eliminated Lovelace dependency** - no longer requires Lovelace API

---

## Summary

### Still Active Enhancements (Available Now)
- ✅ Comprehensive stack update functionality
- ✅ Image pulling and container recreation
- ✅ Enhanced error handling and fallback mechanisms
- ✅ Button state management
- ✅ Enhanced logging and progress tracking
- ✅ Session sharing and connection pooling
- ✅ Simplified integration setup (v0.5.9)

### Removed Enhancements (No Longer Available)
- ⚠️ Automatic dashboard creation (removed in v0.5.9)
- ⚠️ Dashboard services (removed in v0.5.9)
- ⚠️ Dashboard configuration options (removed in v0.5.9)

---

**Note:** All core container and stack management features remain fully functional. The removal of dashboard features allows the integration to focus on reliable container management through Portainer.

