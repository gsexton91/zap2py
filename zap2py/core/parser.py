from dataclasses import dataclass, field
from pathlib import Path
import json, gzip, io, re, os, time
from typing import Any, Dict, Optional
from .utils import pout, perr, pverbose, hour_to_millis, str2time1
from .cache import Cache
from .network import Client

URL_ROOT = "https://tvlistings.gracenote.com/"
URL_ASSETS = "https://zap2it.tmsimg.com/assets/"

@dataclass
class State:
    programs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    stations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    schedule: Dict[str, Dict[int, Dict[str, Any]]] = field(default_factory=dict)
    XTVD_start: int | None = None
    XTVD_end: int | None = None
    tba_found: bool = False
    exp_found: bool = False

class Engine:
    def __post_init__(self): pass
    def __init__(self, opts):
        self.o = opts
        self.state = State()
        self.cache = Cache(Path(self.o.c))
        self.client = Client(self.o)
        self.total_bytes = 0
        self.http_requests = 0
        self.sockets_used = set()
        self.o.engine_ref = self
        self.zap_token: Optional[str] = None
        self.zap_pref = "-"
        self.userEmail = self.o.u or ""
        self.password = self.o.p or ""
        self.postalcode = None
        self.country = None
        self.lineupId = None
        self.device = None
        self.zlineupId = self.o.Y
        self.zipcode = self.o.Z
        self.lang = self.o.l or "en"
        # new overview stats and skip set
        self.failed_overview = set()
        self.overview_success = 0
        self.overview_fail = 0

    def login(self):
        if (not self.userEmail or not self.password) and not self.zlineupId:
            raise SystemExit("Unable to login: Unspecified username or password.")
        if self.userEmail and self.password:
            pout(f'Logging in as "{self.userEmail}"', self.o.q)
            payload = {"emailid": self.userEmail, "password": self.password, "usertype": "0", "facebookuser": "false"}
            r = self.client.request("POST", URL_ROOT + "api/user/login", data=payload)
            if not r.ok:
                raise SystemExit("Login failed")
            t = r.json()
            self.zap_token = t.get("token")
            pref = ""
            if t.get("isMusic"): pref += "m"
            if t.get("isPPV"):   pref += "p"
            if t.get("isHD"):    pref += "h"
            self.zap_pref = ",".join(list(pref)) if pref else "-"
            prs = t.get("properties", {})
            self.postalcode = prs.get("2002")
            self.country = prs.get("2003")
            lu = prs.get("2004", "")
            if ":" in (lu or ""):
                self.lineupId, self.device = lu.split(":", 1)
            else:
                self.lineupId = lu or None
                self.device = "-"
        else:
            pout(f'Connecting with lineupId "{self.zlineupId}"', self.o.q)

    def get_z_token(self) -> str:
        if not self.zap_token:
            self.login()
        return self.zap_token or ""

    def get_zap_params(self) -> dict[str, Any]:
        ph: Dict[str, Any] = {}
        if self.zlineupId or self.zipcode:
            self.postalcode = self.zipcode
            self.country = "USA"
            if self.zlineupId and ":" in self.zlineupId:
                self.lineupId, self.device = self.zlineupId.split(":", 1)
            else:
                self.lineupId = self.zlineupId
                self.device = "-"
            ph["postalCode"] = self.postalcode or ""
        else:
            ph["token"] = self.get_z_token()
        ph["lineupId"] = f"{self.country}-{self.lineupId}-DEFAULT" if self.country and self.lineupId else ""
        ph["postalCode"] = self.postalcode or ""
        ph["countryCode"] = self.country or ""
        ph["headendId"] = self.lineupId or ""
        ph["device"] = self.device or "-"
        ph["aid"] = "orbebb"
        return ph

    def gparams_str(self) -> str:
        import urllib.parse as _u
        h = self.get_zap_params()
        h["country"] = h.pop("countryCode", "")
        return "&".join([f"{k}={_u.quote(str(v))}" for k, v in h.items()])

    def postJSONO(self, pid: str, sid: str):
        """
        Mimic Perl zap2xml behavior exactly:
        - Respect -S delay
        - Retry handled in network client
        - On failure after retries, skip and move on
        """
        if not sid:
            return
        if sid in self.failed_overview:
            return

        fn = self.cache.path(f"O{pid}.js.gz")
        data = None

        if fn.exists():
            pverbose(self.o, f"[cache hit] {fn}")
            try:
                data = self.cache.read_gz_json(fn)
            except Exception as e:
                perr(f"[WARN] Could not read {fn}: {e}")

        if data is None:
            payload = {"programSeriesID": sid, "clickstream[FromPage]": "TV%20Grid"}
            pverbose(self.o, f"[POST] Fetching overview for {pid} (series {sid})")
            time.sleep(self.o.S)

            r = self.client.request("POST", URL_ROOT + "api/program/overviewDetails", data=payload)
            if not (getattr(r, "ok", False) and getattr(r, "content", b"")):
                perr(f"[FAIL] All {self.o.r} attempts failed for {URL_ROOT}api/program/overviewDetails")
                self.failed_overview.add(sid)
                self.overview_fail += 1
                return

            try:
                data = r.json()
                self.cache.write_gz_json(fn, data)
                pverbose(self.o, f"[cache save] {fn}")
                self.overview_success += 1
            except Exception as e:
                perr(f"[WARN] Failed to parse/save overview for {pid} (sid {sid}): {e}")
                self.failed_overview.add(sid)
                self.overview_fail += 1
                return

        P = self.state.programs.setdefault(pid, {})
        tab = data.get("overviewTab") or {}
        desc = tab.get("longDescription") or tab.get("shortDescription")
        if desc:
            P["description"] = desc

        genres = tab.get("genres")
        if isinstance(genres, list):
            for i, g in enumerate(genres, 1):
                gname = (g.get("genreName") or g.get("title")) if isinstance(g, dict) else str(g)
                if gname:
                    P.setdefault("genres", {})[gname.lower()] = i

        for c in tab.get("cast") or []:
            role = str(c.get("role") or c.get("billing")).lower()
            name = c.get("fullName") or c.get("name")
            if not name:
                continue
            if role in ("actor","actress","voice","voice actor","voice talent"):
                P.setdefault("actor", []).append(name)
            elif role in ("host","presenter"):
                P.setdefault("presenter", []).append(name)
            elif role in ("director","dir"):
                P.setdefault("director", []).append(name)
            elif role in ("producer","exec producer","executive producer"):
                P.setdefault("producer", []).append(name)
            elif role in ("writer","screenplay","screenwriter"):
                P.setdefault("writer", []).append(name)
            else:
                P.setdefault("guest", []).append(name)

        for c in tab.get("crew") or []:
            job = str(c.get("job") or "").lower()
            name = c.get("fullName") or c.get("name")
            if not name:
                continue
            if "director" in job:
                P.setdefault("director", []).append(name)
            elif "producer" in job:
                P.setdefault("producer", []).append(name)
            elif "writer" in job or "screen" in job:
                P.setdefault("writer", []).append(name)

        oad = data.get("originalAirDate") or tab.get("originalAirDate")
        if oad:
            try:
                ds = re.sub(r"[^\d]", "", str(oad))
                if ds:
                    P["originalAirDate"] = ds
            except Exception:
                pass

        sr = tab.get("starRating") or data.get("starRating")
        try:
            if sr is not None:
                P["starRating"] = float(sr)
        except Exception:
            pass

        rating = tab.get("rating") or data.get("rating")
        if isinstance(rating, dict):
            code = rating.get("code") or rating.get("rating")
            if code:
                P["rating"] = code
        elif isinstance(rating, str):
            P["rating"] = rating

    def parse_grid_gz(self, gz_path: Path):
        with gzip.open(gz_path, "rb") as fh:
            buffer = fh.read().decode("utf-8", errors="ignore")
        t = json.loads(buffer)
        st = self.state
        for s in t.get("channels", []):
            if "channelId" not in s:
                continue
            cs = f"{s.get('channelNo')}.{s.get('channelId')}"
            st.stations.setdefault(cs, {})
            st.stations[cs]["stnNum"] = s.get("channelId")
            st.stations[cs]["name"] = s.get("callSign")
            st.stations[cs]["number"] = re.sub(r"^0+", "", str(s.get("channelNo") or ""))
            if "order" not in st.stations[cs]:
                st.stations[cs]["order"] = st.stations[cs]["number"]
            events = s.get("events") or []
            if isinstance(events, dict):
                events = events.get("event") or []
            for e in events:
                program = e.get("program", {}) or {}
                cp = program.get("id")
                if not cp:
                    continue
                pverbose(self.o, f"[D] Parsing: {cp}")
                P = st.programs.setdefault(cp, {})
                title = program.get("title")
                if title:
                    P["title"] = title
                try:
                    dur = int(e.get("durationInSeconds") or e.get("duration") or 0)
                except Exception:
                    dur = 0
                if dur > 0:
                    P["duration"] = dur
                if program.get("releaseYear"): P["movie_year"] = program.get("releaseYear")
                if program.get("season"): P["seasonNum"] = program.get("season")
                if program.get("episode"): P["episodeNum"] = program.get("episode")
                if e.get("thumbnail"): P["imageUrl"] = f"{URL_ASSETS}{e.get('thumbnail')}.jpg"
                start = e.get("startTime") or e.get("startDateTime")
                end = e.get("endTime") or e.get("endDateTime")
                try:
                    sch = str2time1(start) * 1000 if start else 0
                    end_ms = str2time1(end) * 1000 if end else (sch + dur * 1000)
                except Exception:
                    continue
                st.schedule.setdefault(cs, {}).setdefault(sch, {})
                st.schedule[cs][sch].update({
                    "time": sch,
                    "endtime": end_ms,
                    "program": cp,
                    "station": cs,
                })
                if self.o.D and program.get("seriesId"):
                    try:
                        self.postJSONO(cp, program.get("seriesId"))
                    except Exception as _ex:
                        perr(f"postJSONO failed for {cp}: {_ex}")

    def run(self):
        from .utils import pout, hour_to_millis
        from .xmltv import write_header, write_footer, write_channels, write_programmes
        import sys
        pout("zap2xml (modular python-port)", self.o.q)
        pout("Command line: " + " ".join(sys.argv), self.o.q)
        import time
        self._start = time.time()
        parse_start = time.time()
        gridHours = 3
        maxCount = self.o.d * (24 // gridHours)
        offset = self.o.s * 3600 * 24 * 1000
        ms = hour_to_millis(self.o.s, gridHours, getattr(self.o, "g", False)) + offset
        if not getattr(self.o, "a", False):
            self.login()
        for count in range(maxCount):
            if count == 0:
                self.state.XTVD_start = ms
            elif count == maxCount - 1:
                self.state.XTVD_end = ms + (gridHours * 3_600_000) - 1
            fn = self.cache.path(f"{ms}.js.gz")
            if not fn.exists():
                zstart = str(ms)[:-3]
                params = f"?time={zstart}&timespan={gridHours}&pref={self.zap_pref}&" + self.gparams_str() + "&TMSID=&AffiliateID=orbebb&FromPage=TV%20Grid&ActivityID=1&OVDID=&isOverride=true"
                url = URL_ROOT + "api/grid" + params
                rs = self.client.get_text(url, er_ok=True)
                if rs == "":
                    break
                self.cache.write_gz_bytes(fn, rs.encode("utf-8"))
            pout(f"[{count+1}/{maxCount}] Parsing: {fn}", self.o.q)
            self.parse_grid_gz(fn)
            self.state.tba_found = False
            self.state.exp_found = False
            ms += gridHours * 3_600_000
        enc = "UTF-8" if getattr(self.o, "U", False) else "ISO-8859-1"
        FH = sys.stdout if self.o.o == '-' else open(self.o.o, "w", encoding=enc, errors="ignore")

        parse_start = time.time()
        with FH:
            write_header(FH, enc)
            write_channels(FH, self.state.stations, getattr(self.o, "U", False), self.o, self.lang)
            write_programmes(FH, self.state, getattr(self.o, "U", False), self.o, self.lang)
            write_footer(FH)

        parse_time = int(time.time() - parse_start)
        total_time = int(time.time() - self._start)
        pout(f"Downloaded {self.total_bytes} bytes in {self.http_requests} http requests using {len(self.sockets_used) or 1} sockets.", self.o.q)
        pout(f"Overview requests: {self.overview_success} succeeded, {self.overview_fail} failed.", self.o.q)
        pout(f"Writing XML file: {self.o.o}", self.o.q)
        pout(f"Completed in {total_time}s (Parse: {parse_time}s) {len(self.state.stations)} stations, {len(self.state.programs)} programs, {sum(len(v) for v in self.state.schedule.values())} scheduled.", self.o.q)
