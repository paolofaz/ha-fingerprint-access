"""Constants for Fingerprint Access."""

DOMAIN = "fingerprint_access"

CONF_EVENT_PREFIX = "event_prefix"
CONF_FULL_ACTIONS = "full_actions"
CONF_PARTIAL_ACTIONS = "partial_actions"
CONF_TEST_MODE = "test_mode"

PROFILE_FULL = "full"
PROFILE_PARTIAL = "partial"
PROFILES = (PROFILE_FULL, PROFILE_PARTIAL)

SUFFIX_MATCH = "_finger_matched"
SUFFIX_SCAN = "_enrollment_scan"
SUFFIX_DONE = "_enrollment_done"
SUFFIX_FAILED = "_enrollment_failed"

EVENT_ACCESS = "fingerprint_access_access"
STORAGE_VERSION = 1
ENROLLMENT_TIMEOUT = 120
DEFAULT_EVENT_PREFIX = "esphome.impronte3q"
