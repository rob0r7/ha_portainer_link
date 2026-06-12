# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-06-12

### Fixed
- Centralized Portainer API/session lifecycle through one coordinator per config entry.
- Removed entity-level polling that caused excessive DNS/API traffic.
- Fixed stopped-container uptime to report not running/unknown instead of stale elapsed time.
- Fixed documented reload and refresh services by registering service handlers.
- Fixed Home Assistant 2026 options-flow compatibility.
- Added stable container device identifiers that survive Docker container ID changes.
- Added native update entities and corrected update availability to use cached coordinator image data.
- Reworked update availability detection to compare full OCI manifest digests and avoid false positives for multi-arch images or images without local `RepoDigests`.

### Changed
- Added runtime options for feature toggles, polling intervals, update-check intervals, SSL verification, and optional notification target.
- Enabled update sensors by default, with infrequent cached registry checks to avoid registry load.
- Removed unused `requests` manifest requirement.

## [0.5.9] - 2025-12-07

### Removed
- Removed automatic Lovelace dashboard creation functionality
- Removed `ha_portainer_link.create_dashboard` service
- Removed `ha_portainer_link.diagnose_dashboard` service
- Removed dashboard configuration options from config flow
- Removed dashboard-related code and dependencies

### Changed
- Simplified integration setup by removing dashboard creation step
- Config flow now directly creates entry after basic configuration
- Reduced codebase complexity by removing dashboard implementation

## [0.5.8] - 2025-12-06

### Fixed
- Fixed silent failures in automatic dashboard creation
- Improved error logging to make dashboard creation failures visible in logs
- Changed debug/warning level logs to error level for dashboard creation issues
- Added full exception stack traces to dashboard creation error logs
- Enhanced error messages when Lovelace dashboard store cannot be found

### Changed
- Dashboard creation errors now log at ERROR level instead of WARNING/DEBUG for better visibility
- Improved diagnostic messages to help identify dashboard creation failures

## [0.5.7] - 2025-12-06

### Fixed
- Improved dashboard creation compatibility with multiple Home Assistant versions
- Enhanced error handling in dashboard creation service
- Fixed dashboard rebuild logic for delayed entity loading

### Changed
- Improved dashboard creation logging and error messages
- Enhanced compatibility detection for Lovelace dashboard API

## [0.5.6] - 2025-12-05

### Fixed
- Dashboard creation stability improvements
- Fixed entity grouping for dashboard views
- Improved stack detection in dashboard generation

## [0.5.5] - 2025-12-04

### Fixed
- Enhanced dashboard API detection for newer Home Assistant versions
- Improved error recovery in dashboard creation process
- Fixed dashboard metadata synchronization

## [0.5.4] - 2025-12-03

### Fixed
- Dashboard creation compatibility fixes for Home Assistant 2024.x
- Improved Lovelace dashboard store detection
- Enhanced fallback mechanisms for dashboard API access

## [0.5.3] - 2025-12-02

### Fixed
- Improved dashboard entity sorting and grouping
- Fixed dashboard view slug generation
- Enhanced error handling for missing entities in dashboard

## [0.5.2] - 2025-12-01

### Fixed
- Dashboard creation timing issues resolved
- Improved delayed dashboard rebuild functionality
- Enhanced entity discovery for dashboard generation

## [0.5.1] - 2025-11-30

### Fixed
- Dashboard creation service error handling improvements
- Fixed dashboard path and title configuration
- Enhanced logging for dashboard operations

## [0.5.0] - 2025-11-25

### Added
- Automatic Lovelace dashboard creation with organized views
- Dashboard service `ha_portainer_link.create_dashboard` for manual dashboard creation
- Automatic dashboard generation during integration setup
- Home view with global container update overview
- Stack-specific views with container controls and status
- Standalone container view for non-stack containers
- Configurable dashboard title and URL path during setup
- Delayed dashboard rebuild to include all entities after initial load
- Dashboard configuration options in config flow

### Changed
- Integration now automatically creates dashboard on setup (configurable)
- Dashboard organizes containers by stack with dedicated views
- Improved entity organization in dashboard views

## [0.4.1] - 2025-11-15

### Fixed
- Fixed excessive DNS queries from frequent update checks (GitHub issue #19)
- Implemented 5-minute minimum throttle for update checks in coordinator
- Enhanced rate limiting and caching to prevent excessive registry queries
- Reduced DNS query volume by throttling update checks to maximum once per 5 minutes
- Minor bug fixes and stability improvements
- Enhanced error messages for better troubleshooting

## [0.4.0] - 2025-08-08

### Added
- Comprehensive stack update functionality with multi-step process
- Image pulling for all containers in a stack before update
- Container recreation with proper cleanup and redeployment
- Robust error handling and fallback mechanisms
- Button state management during stack updates
- Enhanced logging and progress tracking for stack operations

### Changed
- Completely reworked stack update process for better reliability
- Enhanced user feedback during stack update operations
- Improved error recovery with automatic fallback mechanisms
- Updated documentation to reflect new stack update capabilities

### Fixed
- Fixed excessive DNS queries by implementing comprehensive session sharing across all API modules
- Reduced DNS lookups through connection pooling and session reuse (addresses GitHub issue #19)
- Entity category configuration for version sensors
- Device registry warnings in Home Assistant logs
- Integration mode handling and feature toggling
- Configuration flow and migration handling

## [0.3.8] - 2024-08-11

### Changed
- Disabled stack update buttons due to reliability issues
- Fixed entity category errors for version sensors (CONFIG → DIAGNOSTIC)
- Removed device registry warnings by eliminating via_device references
- Improved integration stability and error handling

### Fixed
- Entity category configuration for version sensors
- Device registry warnings in Home Assistant logs
- Integration mode handling and feature toggling
- Configuration flow and migration handling

## [0.3.7] - 2025-01-07

### Fixed
- Indentation error in stack update fallback logic
- Stack update error handling for better reliability
- Enhanced debugging output for troubleshooting stack update issues

## [0.3.6] - 2025-01-06

### Fixed
- Stack update recreation issue (containers deleted but not recreated)
- Enhanced stack update process with proper file content retrieval
- Added multiple fallback mechanisms for failed updates

### Changed
- Improved timing with cleanup delays and extended refresh cycles
- Enhanced debugging and error recovery for stack operations

## [0.3.5] - 2025-01-05

### Fixed
- Device registry warnings
- Config flow deprecation warnings
- Binary sensor entity categories
- Container state handling
- SSL certificate handling

### Changed
- Simplified integration modes (Lightweight/Full)
- Better error messages and debugging
- Optimized performance and reduced log noise

## [0.3.4] - 2025-01-04

### Added
- Automatic SSL verification with fallback
- Missing services.yaml file for proper service registration

### Fixed
- Migration handler for config entries from older versions
- Connection issues error handling
- Container state synchronization

### Changed
- Cleaned up unused imports to reduce log noise
- Enhanced migration to handle all version upgrades properly

## [0.3.3] - 2025-01-03

### Changed
- Simplified configuration to two modes (Lightweight/Full)
- Improved device hierarchy organization

### Fixed
- Container switch state synchronization

## [0.3.2] - 2025-01-02

### Added
- Integration modes (Lightweight, Full, Custom)
- Configurable update intervals
- Docker Hub rate limiting protection

## [0.3.1] - 2025-01-01

### Changed
- Refactored to modular API architecture
- Added DataUpdateCoordinator for better performance

### Added
- Automatic container discovery

## [0.3.0] - 2024-12-31

### Changed
- Complete rewrite with modern Home Assistant patterns
- Added stack clustering and organization

### Added
- Comprehensive error handling

---

## [Unreleased]

### Planned
- Re-enable stack update functionality with improved reliability
- Enhanced error recovery mechanisms
- Additional monitoring capabilities
