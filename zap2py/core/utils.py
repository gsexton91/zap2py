import re, sys
from datetime import datetime, timedelta, timezone

S_TBA = r"\bTBA\b|To Be Announced"

def pout(s: str, quiet: bool):
    if not quiet:
        sys.stdout.write(s if s.endswith("\n") else s + "\n")
        sys.stdout.flush()

def perr(s: str):
    sys.stderr.write(s if s.endswith("\n") else s + "\n")
    sys.stderr.flush()

def pverbose(opts, msg: str):
    if getattr(opts, "v", False):
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

def rtrim(s: str) -> str:
    return re.sub(r"\s+$", "", s)

def _rtrim3(ms: int) -> int:
    return int(str(ms)[:-3]) if isinstance(ms, int) else int(str(int(ms))[:-3])

def conv_time(ms: int, shift_minutes: int) -> str:
    ms += shift_minutes * 60 * 1000
    ts = _rtrim3(ms)
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y%m%d%H%M%S")

def conv_oad(ms: int) -> str:
    ts = _rtrim3(ms)
    return datetime.utcfromtimestamp(ts).strftime("%Y%m%d")

def timezone_suffix(ms: int) -> str:
    ts = _rtrim3(ms)
    dt_local = datetime.fromtimestamp(ts).astimezone()
    offset = dt_local.utcoffset() or timedelta(0)
    total_min = int(offset.total_seconds() // 60)
    sign = "+" if total_min >= 0 else "-"
    total_min = abs(total_min)
    hh = total_min // 60
    mm = total_min % 60
    return f"{sign}{hh:02d}{mm:02d}"

def hour_to_millis(start_day_offset: int, grid_hours: int, use_gmt: bool) -> int:
    now = datetime.now()
    if start_day_offset == 0:
        hour = (now.hour // grid_hours) * grid_hours
        base = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    else:
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if not use_gmt:
        base = base.astimezone(timezone.utc)
    return int(base.timestamp()) * 1000

def str2time1(zs: str) -> int:
    # 'YYYY-mm-ddTHH:MM:SSZ' -> epoch seconds
    return int(datetime.strptime(zs, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())

def xml_escape(text: str, encode_utf8: bool, enc_flags, numeric_entities: bool) -> str:
    if text is None:
        return ""
    t = str(text)
    do_amp = (enc_flags is None) or ("amp" in enc_flags)
    do_quot = (enc_flags is None) or ("quot" in enc_flags)
    do_apos = (enc_flags is None) or ("apos" in enc_flags)
    do_lt = (enc_flags is None) or ("lt" in enc_flags)
    do_gt = (enc_flags is None) or ("gt" in enc_flags)
    if do_amp:  t = t.replace("&", "&amp;")
    if do_quot: t = t.replace('"', "&quot;")
    if do_apos: t = t.replace("'", "&apos;")
    if do_lt:   t = t.replace("<", "&lt;")
    if do_gt:   t = t.replace(">", "&gt;")
    if numeric_entities:
        def repl(m): return f"&#{ord(m.group(0))};"
        t = re.sub(r"[^\x20-\x7F]", repl, t)
    return t
