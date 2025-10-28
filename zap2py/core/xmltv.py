from .utils import xml_escape, conv_time, timezone_suffix, conv_oad

def station_to_channel(st, key: str) -> str:
    return f"I{st[key]['number']}.{st[key]['stnNum']}.zap2it.com"

def write_header(fh, enc: str):
    fh.write(f'<?xml version="1.0" encoding="{enc}"?>\n')
    fh.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n\n')
    fh.write('<tv source-info-url="http://tvlistings.zap2it.com/" source-info-name="zap2it.com"')
    fh.write(' generator-info-name="zap2xml" generator-info-url="zap2xml@gmail.com">\n')

def write_footer(fh):
    fh.write("</tv>\n")

def write_channels(fh, stations, enc_utf8, opts, lang):
    keys = sorted(stations.keys(), key=lambda k: (stations[k].get("order"), stations[k].get("stnNum")))
    for key in keys:
        s = stations[key]
        sname = xml_escape(s.get("name",""), enc_utf8, opts.E, opts.e)
        snum = s.get("number")
        fh.write(f'\t<channel id="{station_to_channel(stations, key)}">\n')
        if snum:
            fh.write(f"\t\t<display-name>{snum} {sname}</display-name>\n")
            fh.write(f"\t\t<display-name>{snum}</display-name>\n")
        if sname:
            fh.write(f"\t\t<display-name>{sname}</display-name>\n")
        fh.write("\t</channel>\n")

def write_programmes(fh, state, enc_utf8, opts, lang):
    st = state
    for station in sorted(st.stations.keys(), key=lambda k: (st.stations[k].get("order"), st.stations[k].get("stnNum"))):
        keys = sorted(st.schedule.get(station, {}).keys())
        for i, s_key in enumerate(keys):
            if i == len(keys) - 1 and "endtime" not in st.schedule[station][s_key]:
                continue
            entry = st.schedule[station][s_key]
            p = entry["program"]
            startTime = conv_time(entry["time"], opts.m); startTZ = timezone_suffix(entry["time"])
            if i + 1 < len(keys):
                end_ms = entry.get("endtime", st.schedule[station][keys[i + 1]]["time"])
            else:
                end_ms = entry.get("endtime", entry["time"] + (st.programs.get(p, {}).get("duration", 0) * 1000))
            stopTime = conv_time(end_ms, opts.m); stopTZ = timezone_suffix(end_ms)
            fh.write(f'\t<programme start="{startTime} {startTZ}" stop="{stopTime} {stopTZ}" channel="{station_to_channel(st.stations, entry["station"])}">\n')
            if st.programs.get(p, {}).get("title"):
                fh.write(f'\t\t<title lang="{lang}">{xml_escape(st.programs[p]["title"], enc_utf8, opts.E, opts.e)}</title>\n')
            if st.programs.get(p, {}).get("episode"):
                fh.write(f'\t\t<sub-title lang="{lang}">{xml_escape(st.programs[p]["episode"], enc_utf8, opts.E, opts.e)}</sub-title>\n')
            if st.programs.get(p, {}).get("description"):
                fh.write(f'\t\t<desc lang="{lang}">{xml_escape(st.programs[p]["description"], enc_utf8, opts.E, opts.e)}</desc>\n')
            if st.programs.get(p, {}).get("movie_year"):
                fh.write(f"\t\t<date>{st.programs[p]['movie_year']}</date>\n")
            elif st.programs.get(p, {}).get("originalAirDate"):
                try:
                    fh.write(f"\t\t<date>{conv_oad(int(st.programs[p]['originalAirDate']))}</date>\n")
                except Exception:
                    pass
            if st.programs.get(p, {}).get("genres"):
                for g, order in sorted(st.programs[p]["genres"].items(), key=lambda kv: (kv[1], kv[0])):
                    fh.write(f'\t\t<category lang="{lang}">{(g.capitalize())}</category>\n')
            if st.programs.get(p, {}).get("duration"):
                try:
                    fh.write(f'\t\t<length units="minutes">{int(st.programs[p]["duration"])//60}</length>\n')
                except Exception:
                    pass
            if st.programs.get(p, {}).get("rating"):
                fh.write("\t\t<rating>\n")
                fh.write(f"\t\t\t<value>{st.programs[p]['rating']}</value>\n")
                fh.write("\t\t</rating>\n")
            if st.programs.get(p, {}).get("starRating"):
                try:
                    fh.write("\t\t<star-rating>\n")
                    fh.write(f"\t\t\t<value>{float(st.programs[p]['starRating'])}/4</value>\n")
                except Exception:
                    pass
            xs = xe = None
            if st.programs.get(p, {}).get("seasonNum") and st.programs.get(p, {}).get("episodeNum"):
                sN = int(st.programs[p]["seasonNum"]); eN = int(st.programs[p]["episodeNum"])
                fh.write(f'\t\t<episode-num system="common">S{str(sN).zfill(2)}E{str(eN).zfill(2)}</episode-num>\n')
                xs = sN - 1; xe = eN - 1
            import re as _re
            dd_prog_id = p
            m = _re.match(r"^(..\d{8})(\d{4})", p or "")
            if m:
                dd_prog_id = f"{m.group(1)}.{m.group(2)}"
                fh.write(f'\t\t<episode-num system="dd_progid">{dd_prog_id}</episode-num>\n')
            if xs is not None and xe is not None and xs >= 0 and xe >= 0:
                fh.write(f'\t\t<episode-num system="xmltv_ns">{xs}.{xe}.</episode-num>\n')
            fh.write("\t</programme>\n")
