import os, time, requests
from .utils import perr  # for logging errors

USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)

class Client:
    def __init__(self, opts):
        self.opts = opts
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate"
        })
        if getattr(opts, "P", None):
            self.session.proxies = {"http": opts.P, "https": opts.P}

    def request(self, method: str, url: str, **kwargs):
        """Perform HTTP request with throttle, timeout, retry, and error logging."""
        time.sleep(self.opts.S)  # throttle between requests
        kwargs.setdefault("timeout", 30)  # 30s timeout per request
        max_retries = max(1, min(getattr(self.opts, "r", 3), 20))

        for attempt in range(1, max_retries + 1):
            try:
                r = self.session.request(method, url, **kwargs)
                # track stats
                if hasattr(self.opts, "engine_ref"):
                    eng = getattr(self.opts, "engine_ref")
                    eng.http_requests += 1
                    try:
                        eng.total_bytes += len(r.content or b"")
                        eng.sockets_used.add(getattr(r.raw, "_connection", object()).sock)
                    except Exception:
                        pass

                if r.ok:
                    return r
                else:
                    perr(f"[WARN] HTTP {r.status_code} on attempt {attempt}/{max_retries}: {url}")
            except requests.exceptions.Timeout:
                perr(f"[ERROR] Timeout after {kwargs['timeout']}s on attempt {attempt}/{max_retries}: {url}")
            except requests.exceptions.RequestException as e:
                perr(f"[ERROR] Request failed ({type(e).__name__}): {e}")

            # brief pause before retry
            time.sleep(self.opts.S + 1)

        # all retries failed — return dummy empty response
        perr(f"[FAIL] All {max_retries} attempts failed for {url}")
        return type("DummyResponse", (), {"ok": False, "content": b"", "text": ""})()

    def get_text(self, url: str, er_ok: bool) -> str:
        """Fetch text content with retry-safe request."""
        r = self.request("GET", url)
        if r.ok and r.content:
            try:
                return r.content.decode(r.encoding or "utf-8", errors="strict")
            except Exception:
                return r.text
        if er_ok:
            return ""
        raise SystemExit(1)

