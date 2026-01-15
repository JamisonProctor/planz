class HttpFetcher:
    def fetch(self, url: str) -> str:
        raise NotImplementedError("HTTP fetcher not implemented")

    def cache_key(self, url: str) -> str:
        return url
