# HA Portainer Link v0.3.8 Release Notes

## 🎉 Release Summary

Version 0.3.8 focuses on stability improvements and bug fixes, addressing several critical issues that were affecting the integration's reliability and user experience.

**Release Date**: August 8th, 2025

## 🔧 Key Changes

### Disabled Stack Update Buttons
- **Issue**: Stack update buttons were causing reliability issues and inconsistent behavior
- **Solution**: Temporarily disabled stack update functionality to prevent user frustration
- **Impact**: Users can still use individual container pull update buttons for updating images
- **Future**: Stack update functionality will be re-enabled in a future release with improved reliability

### Fixed Entity Category Errors
- **Issue**: Version sensors were incorrectly configured with `CONFIG` entity category
- **Solution**: Changed entity category to `DIAGNOSTIC` for all version sensors
- **Impact**: Eliminates Home Assistant warnings about invalid entity categories
- **Files Modified**: `sensor.py`

### Removed Device Registry Warnings
- **Issue**: Device registry warnings due to invalid `via_device` references
- **Solution**: Eliminated `via_device` references in device info creation
- **Impact**: Cleaner Home Assistant logs without device registry warnings
- **Files Modified**: `__init__.py`

### Enhanced Integration Stability
- **Improvement**: Better error handling and recovery mechanisms
- **Improvement**: Streamlined configuration flow and migration handling
- **Improvement**: Optimized lightweight and full view mode implementation

## 📋 Technical Details

### Files Modified
- `custom_components/ha_portainer_link/manifest.json` - Version bump to 0.3.8
- `custom_components/ha_portainer_link/button.py` - Disabled stack update buttons
- `custom_components/ha_portainer_link/sensor.py` - Fixed entity categories
- `custom_components/ha_portainer_link/__init__.py` - Removed via_device references
- `README.md` - Updated documentation and release notes
- `CHANGELOG.md` - Added comprehensive changelog
- `.gitignore` - Added proper gitignore for development files

### Breaking Changes
- **Stack Update Buttons**: No longer available (temporarily disabled)
- **Entity Categories**: Version sensors now use `DIAGNOSTIC` instead of `CONFIG`

### Compatibility
- **Home Assistant**: 2023.8.0 or newer (unchanged)
- **Portainer**: CE/EE with API access (unchanged)
- **Python**: 3.9+ (unchanged)

## 🚀 Installation

### HACS (Recommended)
1. Update through HACS interface
2. Restart Home Assistant
3. No configuration changes required

### Manual Installation
1. Replace existing `custom_components/ha_portainer_link` folder
2. Restart Home Assistant
3. Existing configurations will be automatically migrated

## 🔍 Migration Notes

- Existing configurations will be automatically migrated
- Stack update buttons will disappear after restart
- All other functionality remains unchanged
- No user action required for migration

## 🐛 Bug Fixes

1. **Entity Category Errors**: Fixed invalid entity category configuration
2. **Device Registry Warnings**: Eliminated via_device reference warnings
3. **Integration Stability**: Improved error handling and recovery
4. **Configuration Flow**: Enhanced migration and setup process

## 🔮 Future Plans

### v0.3.9 (Planned)
- Re-enable stack update functionality with improved reliability
- Enhanced error recovery mechanisms
- Additional monitoring capabilities

### Long-term Roadmap
- Improved stack update reliability
- Enhanced error reporting
- Additional monitoring features
- Performance optimizations

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/rob0r7/ha_portainer_link/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rob0r7/ha_portainer_link/discussions)

## 🙏 Acknowledgments

Thank you to all users who reported issues and provided feedback that helped improve this release.

---

**Note**: This is a stability-focused release. While we've temporarily disabled stack update buttons, all other functionality remains fully operational and improved.
