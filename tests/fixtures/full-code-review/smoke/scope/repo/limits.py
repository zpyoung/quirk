MAX_RETRIES = 3


def should_retry(attempt):
    return attempt < MAX_RETRIES
