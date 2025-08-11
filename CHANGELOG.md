# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2024-08-11

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
