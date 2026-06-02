BASE_URL = "https://www.bilet.com/sale-api/v1"
TOKEN_ENDPOINT = "/get-token"
LIST_ENDPOINT = "/list"
VENUES_ENDPOINT = "/get-venues"

# How many seconds before JWT expiry to treat the token as expired (buffer)
TOKEN_EXPIRY_BUFFER_SECONDS = 300

# Max concurrent detail fetch workers
DEFAULT_DETAIL_WORKERS = 5

# Delay between detail requests (seconds) — polite crawling
DETAIL_REQUEST_DELAY_SECONDS = 0.3

# Max retry attempts on transient HTTP errors
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2
MAX_RETRY_BACKOFF_SECONDS = 30

# HTTP status codes that warrant a retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Sentinel LocalStartDate for ongoing/date-selectable attractions.
# Using a far-future date ensures:
#   - FindOccurrence always finds the same occurrence across syncs
#   - EventLifecycleService never deactivates (2099 > today always)
#   - Backend query (StartAtUtc==null path) shows event in all date filters
ONGOING_SENTINEL_DATE = "2099-12-31"

ERROR_PREVIEW_LENGTH = 300
