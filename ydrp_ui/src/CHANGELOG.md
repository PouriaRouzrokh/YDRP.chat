# Changelog

## [Unreleased]

### Added

- API client utility to handle authentication and token expiry
- Session expiry detection and automatic redirect to login page
- Alert component for displaying session expiry messages

### Changed

- Updated all API service calls to use the central API client
- Modified login page to detect and display session expiry messages
- Added expired=true parameter to login redirects

### Fixed

- Fixed issue where expired authentication sessions would leave users in a logged-in but non-functional state
- Ensured consistent error handling for API calls across the application
