"""Static constants for the Biletinial affiliate feed provider."""

# Google Merchant / Facebook product feed namespace used for g:* fields.
FEED_NAMESPACE = "http://base.google.com/ns/1.0"

# Only links on this host (or its subdomains) get affiliate parameters appended.
# Items whose <link> points elsewhere are dropped — never trusted as a ticket URL.
ALLOWED_LINK_HOST = "biletinial.com"

# Fixed UTM parameters required by the Biletinial affiliate agreement.
# `a_aid` is appended separately from settings.biletinial_affiliate_id.
AFFILIATE_QUERY_PARAMS = {
    "utm_source": "affiliate",
    "utm_medium": "affiliate-partner",
    "utm_campaign": "buy-ticket",
    "utm_content": "lokalize",
}

# HTTP retry tuning (mirrors other providers' constants).
RETRY_BACKOFF_BASE = 2
MAX_RETRY_BACKOFF_SECONDS = 30
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

ERROR_PREVIEW_LENGTH = 300
DESCRIPTION_MAX_LENGTH = 2000

USER_AGENT = "LokalizeAppBot/1.0 (contact: iletisim.lokalizeapp@gmail.com)"
