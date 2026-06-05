"""HTML report generation."""

import base64
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    GLOBE_SVG, GLOBE_FAVICON, FEEDS,
    MAXMIND_FAVICON_FILE, IPINFO_FAVICON_FILE, IP2LOCATION_FAVICON_FILE, DBIP_FAVICON_FILE, IPLOCATE_FAVICON_FILE,
)
from .stats import compute_pct


def _pct_cls(pct):
    if pct is None:
        return "na"
    return "good" if pct >= 90 else ("warn" if pct >= 50 else "bad")


def _fmt_pct(pct):
    return "N/A" if pct is None else f"{pct:.1f}%"


def _fmt_addrs(n, is_v6):
    if is_v6:
        exp = len(str(n)) - 1
        return f"{n / 10**exp:.1f} &times; 10<sup>{exp}</sup>"
    for threshold, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if n >= threshold:
            return f"{n / threshold:.1f}{suffix}"
    return str(n)


def _favicon_uri(path):
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lstrip(".")
    mime = "image/x-icon" if ext == "ico" else f"image/{ext}"
    return f"data:{mime};base64,{data}"


def _col_widths(has_mm, has_ip, has_i2l, has_dbip=False, has_iplocate=False):
    ncols = (2 if has_mm else 0) + (2 if has_ip else 0) + (2 if has_i2l else 0) + (2 if has_dbip else 0) + (2 if has_iplocate else 0)
    if ncols == 0:
        return (100, 0)
    other = 7.5  # fixed width per provider column in %
    first = max(100 - ncols * other, 20)
    return (first, other)


def pct_cell(pct, provider_start=False):
    ps = " provider-start" if provider_start else ""
    if pct is None:
        return f'<td class="na{ps}">N/A</td>'
    cls = "good" if pct >= 90 else ("warn" if pct >= 50 else "bad")
    return f'<td class="{cls}{ps}">{pct:.1f}%</td>'


def match_cell(val, provider_val, provider_start=False, is_city=False):
    ps = " provider-start" if provider_start else ""
    if val is None:
        return f'<td class="na{ps}">N/A</td>'
    gf_label = "city" if is_city else "country"
    if val:
        tooltip = f'{provider_val} ✓ matches geofeed {gf_label}'
        return f'<td class="good{ps}"><span title="{tooltip}" style="cursor:help" class="icon-ok">{CHECK_SVG}</span></td>'
    tooltip = f'{provider_val or "(none)"} ✗ does not match geofeed {gf_label}'
    return f'<td class="bad{ps}"><span title="{tooltip}" style="cursor:help" class="icon-bad">{XBOX_SVG}</span></td>'

WARN_SVG = '<svg width="14" height="14"><use href="#icon-warn"/></svg>'
CHECK_SVG = '<svg width="14" height="14"><use href="#icon-check"/></svg>'
XBOX_SVG = '<svg width="14" height="14"><use href="#icon-xbox"/></svg>'
ROUTE_SVG = '<svg width="14" height="14"><use href="#icon-eye-off"/></svg>'
ROUTE_OK_SVG = '<svg width="14" height="14"><use href="#icon-eye"/></svg>'
ROUTE_NA_SVG = '<svg width="14" height="14"><use href="#icon-eye-cancel"/></svg>'
RDAP_OK_SVG = '<svg width="14" height="14"><use href="#icon-shield-check"/></svg>'
RDAP_BAD_SVG = '<svg width="14" height="14"><use href="#icon-shield-x"/></svg>'
RDAP_NA_SVG = '<svg width="14" height="14"><use href="#icon-shield"/></svg>'

SVG_SPRITE = """<svg xmlns="http://www.w3.org/2000/svg" style="display:none">
<symbol id="icon-warn" viewBox="0 0 24 24" fill="currentColor"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 1.67c.955 0 1.845 .467 2.39 1.247l.105 .16l8.114 13.548a2.914 2.914 0 0 1 -2.307 4.363l-.195 .008h-16.225a2.914 2.914 0 0 1 -2.582 -4.2l.099 -.185l8.11 -13.538a2.914 2.914 0 0 1 2.491 -1.403zm.01 13.33l-.127 .007a1 1 0 0 0 0 1.986l.117 .007l.127 -.007a1 1 0 0 0 0 -1.986l-.117 -.007zm-.01 -7a1 1 0 0 0 -.993 .883l-.007 .117v4l.007 .117a1 1 0 0 0 1.986 0l.007 -.117v-4l-.007 -.117a1 1 0 0 0 -.993 -.883z"/></symbol>
<symbol id="icon-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 5a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14"/><path d="M9 12l2 2l4 -4"/></symbol>
<symbol id="icon-xbox" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 5a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14"/><path d="M9 9l6 6m0 -6l-6 6"/></symbol>
<symbol id="icon-eye-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M10.585 10.587a2 2 0 0 0 2.829 2.828"/><path d="M16.681 16.673a8.717 8.717 0 0 1 -4.681 1.327c-3.6 0 -6.6 -2 -9 -6c1.272 -2.12 2.712 -3.678 4.32 -4.674m2.86 -1.146a9.055 9.055 0 0 1 1.82 -.18c3.6 0 6.6 2 9 6c-.666 1.11 -1.379 2.067 -2.138 2.87"/><path d="M3 3l18 18"/></symbol>
<symbol id="icon-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"/></symbol>
<symbol id="icon-eye-cancel" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M12 18c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"/><path d="M16 19a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M17 21l4 -4"/></symbol>
<symbol id="icon-shield-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M11.46 20.846a12 12 0 0 1 -7.96 -14.846a12 12 0 0 0 8.5 -3a12 12 0 0 0 8.5 3a12 12 0 0 1 -.09 7.06"/><path d="M15 19l2 2l4 -4"/></symbol>
<symbol id="icon-shield-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M11.46 20.846a12 12 0 0 1 -7.96 -14.846a12 12 0 0 0 8.5 -3a12 12 0 0 0 8.5 3a12 12 0 0 1 -1.047 6.924"/><path d="M19 19m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M17 21l4 -4"/></symbol>
<symbol id="icon-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3"/></symbol>
</svg>"""


def _locode_icon(issues):
    tooltip = "&#10;".join(issues).replace('"', "'")
    return f'<span title="{tooltip}" style="cursor:help" class="icon-warn">{WARN_SVG}</span>'


def _route_icon(prefix, routed, route_match, too_specific):
    if too_specific:
        plen = prefix.split('/')[1]
        tooltip = f'Prefix {prefix} is too specific (/{plen} > max routable) — cannot appear in global routing table'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-na">{ROUTE_NA_SVG}</span>'
    if routed:
        if route_match == prefix:
            tooltip = f'Prefix {prefix} is visible in RIPE RIS routing table'
        elif int(route_match.split('/')[1]) < int(prefix.split('/')[1]):
            tooltip = f'Prefix {prefix} is covered by {route_match} in RIPE RIS routing table'
        else:
            tooltip = f'Prefix {prefix} has more-specific {route_match} visible in RIPE RIS routing table'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-ok">{ROUTE_OK_SVG}</span>'
    tooltip = f'Prefix {prefix} not visible in RIPE RIS routing table'
    return f'<span title="{tooltip}" style="cursor:help" class="icon-bad">{ROUTE_SVG}</span>'


def _route_icon_loc(total, routed, unrouted, too_specific):
    checkable = total - too_specific
    if too_specific == total:
        tooltip = f'All {total} prefix{"es" if total > 1 else ""} too specific to appear in global routing table'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-na">{ROUTE_NA_SVG}</span>'
    parts = []
    if routed:
        parts.append(f'{routed} visible')
    if unrouted:
        parts.append(f'{unrouted} not visible')
    if too_specific:
        parts.append(f'{too_specific} too specific')
    tooltip = f'{" | ".join(parts)} (of {total} prefixes) in RIPE RIS routing table'
    svg = ROUTE_OK_SVG if unrouted == 0 else ROUTE_SVG
    cls = 'icon-ok' if unrouted == 0 else 'icon-bad'
    return f'<span title="{tooltip}" style="cursor:help" class="{cls}">{svg}</span>'


def _rdap_icon(prefix, rdap_url, feed_url):
    if rdap_url is None:
        tooltip = f'Geofeed in RIR: not found for {prefix}'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-na">{RDAP_NA_SVG}</span>'
    if rdap_url == feed_url:
        tooltip = f'Geofeed in RIR: matches feed URL'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-ok">{RDAP_OK_SVG}</span>'
    tooltip = f'Geofeed in RIR: points to {rdap_url} (different from monitored feed URL)'
    return f'<span title="{tooltip}" style="cursor:help" class="icon-warn">{RDAP_BAD_SVG}</span>'


def _rdap_icon_loc(total, with_rdap):
    if with_rdap == 0:
        tooltip = f'Geofeed in RIR: not registered for any prefix in this location'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-na">{RDAP_NA_SVG}</span>'
    if with_rdap == total:
        tooltip = f'All {total} prefix{"es" if total > 1 else ""} have Geofeed in RIR registered'
        return f'<span title="{tooltip}" style="cursor:help" class="icon-ok">{RDAP_OK_SVG}</span>'
    tooltip = f'{with_rdap} of {total} prefixes have Geofeed in RIR registered'
    return f'<span title="{tooltip}" style="cursor:help" class="icon-warn">{RDAP_BAD_SVG}</span>'


def _build_topbar_logo(feed):
    logo_file = feed["logo_file"]
    logo_type = feed.get("logo_type", "svg")
    favicon_uri = ""
    topbar_logo = ""
    if not logo_file.exists():
        return topbar_logo, favicon_uri
    if logo_type == "svg":
        svg_text = logo_file.read_text(encoding="utf-8")
        logo_b64 = base64.b64encode(svg_text.encode()).decode()
        favicon_uri = f"data:image/svg+xml;base64,{logo_b64}"
        if feed.get("logo_invert"):
            topbar_logo = f'<div style="filter:invert(1);display:flex;align-items:center">{svg_text}</div>'
        else:
            topbar_logo = svg_text
    else:
        raw = logo_file.read_bytes()
        b64 = base64.b64encode(raw).decode()
        invert = ' style="height:40px;filter:invert(1)"' if feed.get("logo_invert") else ' style="height:40px"'
        topbar_logo = f'<img src="data:image/png;base64,{b64}"{invert} alt="">'
        favicon_uri = f"data:image/png;base64,{b64}"
    return topbar_logo, favicon_uri


def generate_html(results, stats, has_mm, has_ip, has_i2l, has_dbip=False, has_iplocate=False, feed=None):
    topbar_logo, favicon_uri = _build_topbar_logo(feed)
    title = feed["title"]
    topbar_title = feed.get("topbar_title", title)
    output_path = feed["output"]
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    first_w, other_w = _col_widths(has_mm, has_ip, has_i2l, has_dbip, has_iplocate)
    mm_fav = _favicon_uri(MAXMIND_FAVICON_FILE)
    ip_fav = _favicon_uri(IPINFO_FAVICON_FILE)
    i2l_fav = _favicon_uri(IP2LOCATION_FAVICON_FILE)
    dbip_fav = _favicon_uri(DBIP_FAVICON_FILE)
    iplocate_fav = _favicon_uri(IPLOCATE_FAVICON_FILE)

    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{f'<link rel="icon" href="{favicon_uri}">' if favicon_uri else ''}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/css/flag-icons.min.css">
<style>
  :root {{
    --squid-ink: #232f3e; --squid-ink-light: #37475a; --aws-orange: #ff9900;
    --aws-orange-hover: #ec7211; --text-primary: #16191f; --text-secondary: #545b64;
    --bg-page: #f2f3f3; --bg-card: #ffffff; --border: #d5dbdb; --border-light: #eaeded;
    --good: #037f0c; --good-bg: #f2fcf3; --warn: #8a6d00; --warn-bg: #fef8e7;
    --bad: #d13212; --bad-bg: #fdf3f1; --na-text: #879596;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg-page); color: var(--text-primary); line-height: 1.5; }}
  .topbar {{ background: var(--squid-ink); padding: 12px 32px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.15); }}
  .topbar svg {{ height: 40px; width: auto; }}
  .topbar h1 {{ color: #ffffff; font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }}
  .topbar .separator {{ width: 1px; height: 28px; background: var(--squid-ink-light); }}
  .back-arrow {{ display: inline-block; color: var(--text-secondary); text-decoration: none; font-size: 13px; margin-bottom: 12px; transition: color 0.15s; }}
  .back-arrow:hover {{ color: var(--text-primary); }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px 32px; }}
  .card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
  .card-header {{ padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }}
  .card-header h2 {{ font-size: 18px; font-weight: 700; color: var(--text-primary); }}
  .filter-toggle {{ font-size: 13px; color: var(--text-secondary); cursor: pointer; user-select: none; white-space: nowrap; }}
  .filter-btn {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px; cursor: pointer; display: flex; align-items: center; color: var(--text-secondary); transition: border-color 0.15s, background 0.15s; }}
  .filter-btn:hover {{ border-color: var(--aws-orange); }}
  .filter-btn.active {{ border-color: var(--aws-orange); background: #fff8ee; color: var(--text-primary); }}
  .filter-btn svg {{ pointer-events: none; }}
  .search-box {{ font-size: 13px; padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; outline: none; width: 180px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; }}
  .search-box:focus {{ border-color: var(--aws-orange); }}
  .filter-toggle input {{ vertical-align: middle; margin-right: 4px; cursor: pointer; }}
  .loc-filter {{ font-size: 11px; color: var(--text-secondary); cursor: pointer; user-select: none; margin-left: 8px; font-weight: 400; display: none; }}
  .loc-row.open .loc-filter {{ display: inline; }}
  .loc-filter input {{ vertical-align: middle; margin-right: 2px; cursor: pointer; }}
  .loc-filter-btn {{ background: none; border: 1px solid transparent; border-radius: 4px; padding: 1px 3px; cursor: pointer; display: none; align-items: center; vertical-align: middle; margin-left: 2px; color: var(--text-secondary); }}
  .loc-row.open .loc-filter-btn {{ display: inline-flex; }}
  .loc-filter-btn:hover {{ border-color: var(--aws-orange); }}
  .loc-filter-btn.active {{ border-color: var(--aws-orange); background: #fff8ee; }}
  .loc-filter-sep {{ display: none; width: 1px; height: 14px; background: var(--border); margin: 0 6px; vertical-align: middle; }}
  .loc-row.open .loc-filter-sep {{ display: inline-block; }}
  .loc-counter {{ font-size: 11px; font-weight: 400; color: var(--text-secondary); }}
  .header-counter {{ font-size: 11px; font-weight: 400; opacity: 0.7; }}
  .loc-row.filtered, .prefix-row.filtered {{ display: none !important; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
  th:first-child, td:first-child {{ width: {first_w}%; }}
  th:not(:first-child), td:not(:first-child) {{ width: {other_w}%; }}
  th {{ background: var(--squid-ink); color: #fff; padding: 10px 16px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10; }}
  th.provider-hdr {{ text-align: center; border-left: 2px solid var(--squid-ink-light); background: var(--squid-ink); font-size: 13px; text-transform: uppercase; }}
  th.provider-hdr img {{ height: 16px; width: 16px; vertical-align: middle; margin-right: 6px; }}
  th.sub-hdr {{ text-align: center; font-size: 11px; background: var(--squid-ink-light); text-transform: none; letter-spacing: 0; font-weight: 500; }}
  th.sub-hdr.provider-start {{ border-left: 2px solid var(--squid-ink-light); }}
  td {{ padding: 10px 16px; font-size: 14px; border-bottom: 1px solid var(--border-light); color: var(--text-primary); }}
  .loc-row {{ cursor: pointer; background: var(--bg-card); transition: background 0.15s; }}
  .loc-row:hover {{ background: #f7f8f8; }}
  .loc-row td {{ font-weight: 600; }}
  .loc-row td:first-child {{ padding-left: 20px; }}
  .loc-row td:first-child::before {{ content: ""; display: inline-block; width: 0; height: 0; margin-right: 10px; border-left: 6px solid var(--aws-orange); border-top: 4px solid transparent; border-bottom: 4px solid transparent; transition: transform 0.2s; vertical-align: middle; }}
  .loc-row.open td:first-child::before {{ transform: rotate(90deg); }}
  .prefix-row {{ display: none; }}
  .prefix-row.show {{ display: table-row; }}
  .prefix-row td {{ background: #fafbfc; }}
  .prefix-row td:first-child {{ padding-left: 44px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .prefix-row td:first-child small {{ color: var(--na-text); font-family: "Amazon Ember", -apple-system, sans-serif; }}
  td.good {{ color: var(--good); background: var(--good-bg); font-weight: 600; }}
  td.warn {{ color: var(--warn); background: var(--warn-bg); font-weight: 600; }}
  td.bad {{ color: var(--bad); background: var(--bad-bg); font-weight: 600; }}
  td.na {{ color: var(--na-text); }}
  td.provider-start {{ border-left: 2px solid var(--border-light); }}
  .loc-row td.provider-start {{ border-left: 2px solid var(--border); }}
  td {{ text-align: center; }}
  td:first-child {{ text-align: left; }}
  .stats-bar {{ display: grid; grid-template-columns: auto repeat(3, 1fr); gap: 0; border-bottom: 1px solid var(--border); background: var(--bg-page); }}
  .stats-row-label {{ display: flex; align-items: center; padding: 16px 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary); border-bottom: 1px solid var(--border); }}
  .stats-row-label:last-of-type, .stats-bar .stat-group:nth-last-child(-n+3) {{ border-bottom: none; }}
  .stat-group {{ min-width: 0; padding: 14px 24px; border-bottom: 1px solid var(--border); }}
  .stat-group-title {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary); margin-bottom: 6px; }}
  .stat-items {{ display: flex; gap: 16px; }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat-value {{ font-size: 20px; font-weight: 700; color: var(--text-primary); line-height: 1.2; }}
  .stat-value.good {{ color: var(--good); }} .stat-value.warn {{ color: var(--warn); }} .stat-value.bad {{ color: var(--bad); }}
  .stat-label {{ font-size: 11px; color: var(--text-secondary); }}
  tfoot td {{ background: var(--bg-page); font-size: 12px; font-weight: 600; padding: 8px 16px; border-top: 2px solid var(--border); color: var(--text-secondary); }}
  tfoot td.good {{ color: var(--good); background: var(--good-bg); }}
  tfoot td.warn {{ color: var(--warn); background: var(--warn-bg); }}
  tfoot td.bad {{ color: var(--bad); background: var(--bad-bg); }}
  tfoot td.na {{ color: var(--na-text); }}
  .icon-ok {{ color: var(--good); vertical-align: middle; flex-shrink: 0; }}
  .icon-bad {{ color: var(--bad); vertical-align: middle; flex-shrink: 0; }}
  .icon-warn {{ color: var(--aws-orange); vertical-align: middle; margin-left: 4px; flex-shrink: 0; }}
  .icon-na {{ color: var(--na-text); vertical-align: middle; margin-left: 4px; flex-shrink: 0; }}
</style>
</head>
<body>
{SVG_SPRITE}
<div class="topbar">
  {topbar_logo}
  <div class="separator"></div>
  <h1>{topbar_title}</h1>
</div>
<div class="container">
<a href="index.html" class="back-arrow">&larr; All Reports</a>
<div class="card">
<div class="card-header">
  <h2>Location Validation Results</h2>
  <div style="display:flex;align-items:center;gap:8px">
    <input type="text" id="prefixSearch" placeholder="Search prefix or IP&hellip;" class="search-box">
    <button class="filter-btn" id="filterInaccurate" title="Show only inaccurate locations">{XBOX_SVG}</button>
    <button class="filter-btn" id="filterLocode" title="Show only locations with location name issues">{WARN_SVG}</button>
    <button class="filter-btn" id="filterUnrouted" title="Show only locations with unrouted prefixes">{ROUTE_SVG}</button>
    {'<button class="filter-btn" id="filterRir" title="Show only locations with Geofeed in RIR">'+RDAP_OK_SVG+'</button>' if feed.get('check_rdap') else ''}
  </div>
</div>
<div class="stats-bar">
  <div class="stats-row-label">Prefixes</div>
  <div class="stat-group">
    <div class="stat-group-title">Count</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value">{stats['total']:,}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value">{stats['v4']:,}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value">{stats['v6']:,}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">Country Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct'])}">{_fmt_pct(stats['country_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct_v4'])}">{_fmt_pct(stats['country_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct_v6'])}">{_fmt_pct(stats['country_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">City Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct'])}">{_fmt_pct(stats['city_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct_v4'])}">{_fmt_pct(stats['city_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct_v6'])}">{_fmt_pct(stats['city_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stats-row-label">Addresses</div>
  <div class="stat-group">
    <div class="stat-group-title">Count</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value">{_fmt_addrs(stats['v4_addrs'], False)}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value">{_fmt_addrs(stats['v6_addrs'], True)}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">Country Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct'])}">{_fmt_pct(stats['w_country_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct_v4'])}">{_fmt_pct(stats['w_country_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct_v6'])}">{_fmt_pct(stats['w_country_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">City Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct'])}">{_fmt_pct(stats['w_city_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct_v4'])}">{_fmt_pct(stats['w_city_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct_v6'])}">{_fmt_pct(stats['w_city_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
</div>
<table>
<thead>
<tr>
  <th rowspan="2">Location <span id="locCounter" class="header-counter"></span> <span id="prefixCounter" class="header-counter"></span></th>
  {'<th colspan="2" class="provider-hdr"><img src="' + mm_fav + '" alt="">MaxMind</th>' if has_mm else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + ip_fav + '" alt="">IPinfo</th>' if has_ip else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + dbip_fav + '" alt="">DB-IP</th>' if has_dbip else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + i2l_fav + '" alt="">IP2Location</th>' if has_i2l else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + iplocate_fav + '" alt="">IPLocate</th>' if has_iplocate else ''}
</tr>
<tr>
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_mm else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_ip else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_dbip else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_i2l else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_iplocate else ''}
</tr>
</thead><tbody>""")

    for loc_idx, (country_code, display_name, loc_results) in enumerate(results):
        if not loc_results:
            continue
        mm_c_pct = compute_pct([r[7] for r in loc_results])
        mm_ci_pct = compute_pct([r[8] for r in loc_results])
        ip_c_pct = compute_pct([r[10] for r in loc_results])
        i2l_c_pct = compute_pct([r[13] for r in loc_results])
        i2l_ci_pct = compute_pct([r[14] for r in loc_results])
        dbip_c_pct = compute_pct([r[23] for r in loc_results])
        dbip_ci_pct = compute_pct([r[24] for r in loc_results])
        iplocate_c_pct = compute_pct([r[26] for r in loc_results])
        active = ([7, 8] if has_mm else []) + ([10] if has_ip else []) + ([13, 14] if has_i2l else []) + ([23, 24] if has_dbip else []) + ([26] if has_iplocate else [])
        has_bad = any(any(r[i] is not None and not r[i] for i in active) for r in loc_results)
        cc = country_code.lower()
        flag = f'<span class="fi fi-{cc}" style="margin-right:8px"></span>'
        loc_filter = f'<span class="loc-filter-sep"></span><button class="loc-filter-btn" data-loc="{loc_idx}" data-filter="inaccurate" title="Show only inaccurate prefixes">{XBOX_SVG}</button>'
        loc_filter += f'<button class="loc-filter-btn" data-loc="{loc_idx}" data-filter="unrouted" title="Show only unrouted prefixes">{ROUTE_SVG}</button>'
        if feed.get("check_rdap"):
            loc_filter += f'<button class="loc-filter-btn" data-loc="{loc_idx}" data-filter="rir" title="Show only prefixes with Geofeed in RIR">{RDAP_OK_SVG}</button>'
        # All prefixes share the same location — validate once from the first result
        r0 = loc_results[0]
        locode_issues = r0[15]
        locode_icon = _locode_icon(locode_issues) if locode_issues else ""
        unrouted_count = sum(1 for r in loc_results if not r[16] and not r[18])
        routed_count = sum(1 for r in loc_results if r[16])
        too_specific_count = sum(1 for r in loc_results if r[18])
        route_icon = _route_icon_loc(len(loc_results), routed_count, unrouted_count, too_specific_count)
        rdap_loc_icon = ""
        if feed.get("check_rdap"):
            with_rdap = sum(1 for r in loc_results if r[19] is not None)
            rdap_loc_icon = _rdap_icon_loc(len(loc_results), with_rdap)
        has_locode = 1 if locode_issues else 0
        has_unrouted = 1 if unrouted_count > 0 else 0
        has_rir = 1 if feed.get("check_rdap") and any(r[19] is not None for r in loc_results) else 0
        html.append(f'<tr class="loc-row" data-loc="{loc_idx}" data-has-bad="{int(has_bad)}" data-has-locode="{has_locode}" data-has-unrouted="{has_unrouted}" data-has-rir="{has_rir}">')
        html.append(f"  <td>{flag}{display_name} <span class='loc-count' data-loc-count='{loc_idx}' data-total='{len(loc_results)}'>({len(loc_results)})</span> {locode_icon}{route_icon}{rdap_loc_icon} {loc_filter}</td>")
        if has_mm:
            html.append(f"  {pct_cell(mm_c_pct, True)}{pct_cell(mm_ci_pct)}")
        if has_ip:
            html.append(f'  {pct_cell(ip_c_pct, True)}<td class="na">N/A</td>')
        if has_dbip:
            html.append(f"  {pct_cell(dbip_c_pct, True)}{pct_cell(dbip_ci_pct)}")
        if has_i2l:
            html.append(f"  {pct_cell(i2l_c_pct, True)}{pct_cell(i2l_ci_pct)}")
        if has_iplocate:
            html.append(f'  {pct_cell(iplocate_c_pct, True)}<td class="na">N/A</td>')
        html.append("</tr>")

        for r in sorted(loc_results, key=lambda r: (r[1], r[0])):
            prefix, is_v6, gf_c, gf_sub, gf_ci = r[0], r[1], r[2], r[3], r[4]
            mm_c, mm_ci, mm_c_m, mm_ci_m = r[5], r[6], r[7], r[8]
            ip_c, ip_c_m = r[9], r[10]
            i2l_c, i2l_ci, i2l_c_m, i2l_ci_m = r[11], r[12], r[13], r[14]
            dbip_c, dbip_ci, dbip_c_m, dbip_ci_m = r[21], r[22], r[23], r[24]
            iplocate_c, iplocate_c_m = r[25], r[26]
            proto = "IPv6" if is_v6 else "IPv4"
            active_m = ([mm_c_m, mm_ci_m] if has_mm else []) + ([ip_c_m] if has_ip else []) + ([i2l_c_m, i2l_ci_m] if has_i2l else []) + ([dbip_c_m, dbip_ci_m] if has_dbip else []) + ([iplocate_c_m] if has_iplocate else [])
            perfect = all(m is None or m for m in active_m)
            gf_label = ", ".join(filter(None, [gf_c, gf_sub, gf_ci]))
            routed = r[16]
            route_match = r[17]
            too_specific = r[18]
            rdap_url = r[19]
            route_icon = _route_icon(prefix, routed, route_match, too_specific)
            rdap_icon = _rdap_icon(prefix, rdap_url, feed["url"]) if feed.get("check_rdap") else ""
            prefix_rir = "1" if rdap_url is not None else "0"
            prefix_routed = "0" if (not routed and not too_specific) else "1"
            html.append(f'<tr class="prefix-row" data-loc="{loc_idx}" data-perfect="{int(perfect)}" data-prefix="{prefix}" data-routed="{prefix_routed}" data-has-rir="{prefix_rir}">')
            html.append(f"  <td>{prefix} <small>({proto}) &mdash; geofeed: {gf_label}</small> {route_icon}{rdap_icon}</td>")
            if has_mm:
                html.append(f"  {match_cell(mm_c_m, mm_c, True)}{match_cell(mm_ci_m, mm_ci, is_city=True)}")
            if has_ip:
                html.append(f'  {match_cell(ip_c_m, ip_c, True)}<td class="na">N/A</td>')
            if has_dbip:
                html.append(f"  {match_cell(dbip_c_m, dbip_c, True)}{match_cell(dbip_ci_m, dbip_ci, is_city=True)}")
            if has_i2l:
                html.append(f"  {match_cell(i2l_c_m, i2l_c, True)}{match_cell(i2l_ci_m, i2l_ci, is_city=True)}")
            if has_iplocate:
                html.append(f'  {match_cell(iplocate_c_m, iplocate_c, True)}<td class="na">N/A</td>')
            html.append("</tr>")

    html.append("</tbody>")

    def _foot_label(label):
        return f'<td style="text-align:right;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.5px">{label}</td>'

    def _foot_row(label, mm_c_key, mm_ci_key, ip_c_key, i2l_c_key, i2l_ci_key, dbip_c_key=None, dbip_ci_key=None, iplocate_c_key=None):
        row = f"<tr>{_foot_label(label)}"
        if has_mm:
            row += pct_cell(stats.get(mm_c_key), True) + pct_cell(stats.get(mm_ci_key))
        if has_ip:
            row += pct_cell(stats.get(ip_c_key), True) + '<td class="na">N/A</td>'
        if has_dbip and dbip_c_key:
            row += pct_cell(stats.get(dbip_c_key), True) + pct_cell(stats.get(dbip_ci_key))
        if has_i2l:
            row += pct_cell(stats.get(i2l_c_key), True) + pct_cell(stats.get(i2l_ci_key))
        if has_iplocate and iplocate_c_key:
            row += pct_cell(stats.get(iplocate_c_key), True) + '<td class="na">N/A</td>'
        return row + "</tr>"

    html.append("<tfoot>")
    html.append(_foot_row("Prefix Accuracy", "mm_c", "mm_ci", "ip_c", "i2l_c", "i2l_ci", "dbip_c", "dbip_ci", "iplocate_c"))
    html.append(_foot_row("Address Accuracy", "w_mm_c", "w_mm_ci", "w_ip_c", "w_i2l_c", "w_i2l_ci", "w_dbip_c", "w_dbip_ci", "w_iplocate_c"))
    html.append("</tfoot>")
    html.append(f"""</table>
</div>
</div>
<footer style="text-align:center;padding:16px;font-size:12px;color:#545b64">Last updated: {now_utc}</footer>""")

    raw = "\n".join(html) + _report_js()
    output_path.write_text(_dedup_tooltips(raw), encoding="utf-8")


def _dedup_tooltips(html):
    """Collapse icon spans and deduplicate tooltips into JS lookup tables."""
    import re, json

    # Step 1: collapse <span title="T" style="cursor:help" class="C"><svg ...><use href="#I"/></svg></span>
    # into <i class="ic C" data-i="I" title="T"></i>
    icon_re = re.compile(
        r'<span title="([^"]*)" style="cursor:help" class="([^"]+)">'  
        r'<svg width="14" height="14"><use href="(#[^"]+)"/></svg></span>'
    )
    html = icon_re.sub(lambda m: f'<i class="ic {m.group(2)}" data-i="{m.group(3)}" title="{m.group(1)}"></i>', html)

    # Step 2: deduplicate title= into a JS lookup table
    titles = []
    title_index = {}

    def replace_title(m):
        val = m.group(1)
        if val not in title_index:
            title_index[val] = len(titles)
            titles.append(val)
        return f'data-t="{title_index[val]}"'

    html = re.sub(r'title="([^"]+)"', replace_title, html)

    # Step 3: inject CSS for <i class="ic"> and JS lookup table
    ic_css = '<style>.ic{display:inline-block;width:14px;height:14px;vertical-align:middle;flex-shrink:0;cursor:help;}</style>'
    table_js = (
        'const _T=' + json.dumps(titles, ensure_ascii=False) + ';'
        'document.addEventListener("mouseover",e=>{'
        'const t=e.target.closest("[data-t]");'
        'if(t&&!t.title){t.title=_T[t.dataset.t];}});'
        'document.addEventListener("DOMContentLoaded",()=>{'
        'document.querySelectorAll("i.ic[data-i]").forEach(el=>{'
        'const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");'
        'svg.setAttribute("width","14");svg.setAttribute("height","14");'
        'const use=document.createElementNS("http://www.w3.org/2000/svg","use");'
        'use.setAttribute("href",el.dataset.i);svg.appendChild(use);el.appendChild(svg);});});'
    )
    html = html.replace('</style>\n</head>', ic_css + '</style>\n</head>', 1)
    html = html.replace('</script>\n</body>', table_js + '</script>\n</body>', 1)
    return html
    """Replace repeated title= attributes with data-t= indices into a JS lookup table."""
    import re
    titles = []
    title_index = {}

    def replace(m):
        val = m.group(1)
        if val not in title_index:
            title_index[val] = len(titles)
            titles.append(val)
        return f'data-t="{title_index[val]}"'

    html = re.sub(r'title="([^"]+)"', replace, html)
    # Inject lookup table + mouseover handler before </script>
    table_js = 'const _T=' + __import__('json').dumps(titles, ensure_ascii=False) + ';'
    table_js += 'document.addEventListener("mouseover",e=>{const t=e.target.closest("[data-t]");if(t){t.title=_T[t.dataset.t];}});'
    html = html.replace('</script>', table_js + '</script>', 1)
    return html


def _report_js():
    return """
<script>
function parseIP(s) {
  if (s.includes(':')) {
    const parts = s.split(':');
    const full = [];
    for (let i = 0; i < parts.length; i++) {
      if (parts[i] === '') {
        const fill = 8 - parts.filter(p => p !== '').length;
        for (let j = 0; j < fill; j++) full.push(0n);
      } else { full.push(BigInt(parseInt(parts[i], 16))); }
    }
    if (full.length !== 8) return null;
    let n = 0n;
    for (const p of full) n = (n << 16n) | p;
    return { bits: n, ver: 6 };
  }
  const p = s.split('.');
  if (p.length !== 4 || p.some(x => isNaN(x) || x < 0 || x > 255 || x === '')) return null;
  return { bits: BigInt(p[0]) << 24n | BigInt(p[1]) << 16n | BigInt(p[2]) << 8n | BigInt(p[3]), ver: 4 };
}
function parsePrefix(cidr) {
  const [addr, lenStr] = cidr.split('/');
  const ip = parseIP(addr);
  if (!ip) return null;
  const len = BigInt(lenStr);
  const total = ip.ver === 6 ? 128n : 32n;
  const mask = ((1n << total) - 1n) ^ ((1n << (total - len)) - 1n);
  return { net: ip.bits & mask, mask, ver: ip.ver };
}
function ipInPrefix(ip, prefix) {
  if (ip.ver !== prefix.ver) return false;
  return (ip.bits & prefix.mask) === prefix.net;
}
function applyFilters() {
  const filterInaccurate = document.getElementById('filterInaccurate')?.classList.contains('active');
  const filterLocode = document.getElementById('filterLocode')?.classList.contains('active');
  const filterUnrouted = document.getElementById('filterUnrouted')?.classList.contains('active');
  const filterRir = document.getElementById('filterRir')?.classList.contains('active');
  const query = document.getElementById('prefixSearch').value.trim().toLowerCase();
  const searching = query.length > 0;
  const filtering = filterInaccurate || filterLocode || filterUnrouted || filterRir || searching;
  const searchIP = searching ? parseIP(query) : null;
  let visibleLocs = 0, totalLocs = 0, visiblePfx = 0, totalPfx = 0;
  document.querySelectorAll('.loc-row').forEach(row => {
    const id = row.dataset.loc;
    const hasBad = row.dataset.hasBad === '1';
    const hasLocode = row.dataset.hasLocode === '1';
    const hasUnrouted = row.dataset.hasUnrouted === '1';
    const hasRir = row.dataset.hasRir === '1';
    const prefixes = document.querySelectorAll(`.prefix-row[data-loc="${id}"]`);
    const local = row.querySelector('.locFilter');
    const localOn = local && local.checked;
    const locInaccurate = row.querySelector('.loc-filter-btn[data-filter="inaccurate"]')?.classList.contains('active');
    const locUnrouted = row.querySelector('.loc-filter-btn[data-filter="unrouted"]')?.classList.contains('active');
    const locRir = row.querySelector('.loc-filter-btn[data-filter="rir"]')?.classList.contains('active');
    const countEl = document.querySelector(`[data-loc-count="${id}"]`);
    const total = prefixes.length;
    let visible = 0;
    prefixes.forEach(r => {
      let hidden = false;
      if ((filterInaccurate || localOn || locInaccurate) && r.dataset.perfect === '1') hidden = true;
      if ((filterUnrouted || locUnrouted) && r.dataset.routed !== '0') hidden = true;
      if ((filterRir || locRir) && r.dataset.hasRir !== '1') hidden = true;
      if (searching) {
        let match = r.dataset.prefix.indexOf(query) !== -1;
        if (!match && searchIP) {
          const pfx = parsePrefix(r.dataset.prefix);
          if (pfx) match = ipInPrefix(searchIP, pfx);
        }
        if (!match) hidden = true;
      }
      r.classList.toggle('filtered', hidden);
      if (!hidden) visible++;
    });
    totalPfx += total;
    visiblePfx += visible;
    let hideRow = false;
    if (filterInaccurate && !hasBad) hideRow = true;
    if (filterLocode && !hasLocode) hideRow = true;
    if (filterUnrouted && !hasUnrouted) hideRow = true;
    if (filterRir && !hasRir) hideRow = true;
    if (searching && visible === 0) hideRow = true;
    row.classList.toggle('filtered', hideRow);
    totalLocs++;
    if (!hideRow) { visibleLocs++; visiblePfx += visible; totalPfx += total; }
    else { totalPfx += total; }
    const isFiltered = (filterInaccurate || localOn || locInaccurate || filterUnrouted || locUnrouted || filterRir || locRir || searching) && visible < total;
    countEl.textContent = isFiltered ? `(${visible} / ${total})` : `(${total})`;
    if (searching && visible > 0 && !row.classList.contains('open')) {
      row.classList.add('open');
      prefixes.forEach(r => r.classList.add('show'));
    }
  });
  const hdr = document.getElementById('locCounter');
  hdr.textContent = filtering ? `${visibleLocs} / ${totalLocs} locations` : '';
  const pfxHdr = document.getElementById('prefixCounter');
  pfxHdr.textContent = filtering ? `| ${visiblePfx} / ${totalPfx} prefixes` : '';
}
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.classList.toggle('active');
    applyFilters();
  });
});
document.addEventListener('click', e => {
  const btn = e.target.closest('.loc-filter-btn');
  if (btn) {
    e.stopPropagation();
    btn.classList.toggle('active');
    applyFilters();
    return;
  }
  const sep = e.target.closest('.loc-filter-sep');
  if (sep) {
    e.stopPropagation();
  }
});
document.querySelectorAll('.loc-filter').forEach(lbl => {
  lbl.addEventListener('click', e => e.stopPropagation());
});
document.getElementById('prefixSearch').addEventListener('input', applyFilters);
document.querySelectorAll('.locFilter').forEach(cb => {
  cb.addEventListener('change', e => { e.stopPropagation(); applyFilters(); });
  cb.addEventListener('click', e => e.stopPropagation());
});
document.querySelectorAll('.loc-filter').forEach(lbl => {
  lbl.addEventListener('click', e => e.stopPropagation());
});
document.querySelectorAll('.loc-row').forEach(row => {
  row.addEventListener('click', (e) => {
    if (e.target.closest('.loc-filter-btn') || e.target.closest('.loc-filter-sep') || e.target.closest('.loc-filter')) return;
    const id = row.dataset.loc;
    row.classList.toggle('open');
    document.querySelectorAll(`.prefix-row[data-loc="${id}"]`).forEach(r => r.classList.toggle('show'));
  });
});
</script>
</body></html>"""


def generate_index(feeds, feed_stats):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = []
    for feed, stats in zip(feeds, feed_stats):
        card_file = feed.get("card_logo_file", feed["logo_file"])
        card_type = feed.get("card_logo_type", feed["logo_type"])
        if card_file.exists():
            if card_type == "svg":
                logo_html = card_file.read_text(encoding="utf-8")
            else:
                b64 = base64.b64encode(card_file.read_bytes()).decode()
                logo_html = f'<img src="data:image/png;base64,{b64}" alt="">'
        else:
            logo_html = ""
        href = feed["output"].name
        country_pct = _fmt_pct(stats.get("country_pct"))
        city_pct = _fmt_pct(stats.get("city_pct"))
        total = stats.get("total", 0)
        country_pct = _fmt_pct(stats.get("country_pct"))
        city_pct = _fmt_pct(stats.get("city_pct"))
        total = stats.get("total", 0)
        if not total:
            stats_html = '<div class="card-stats"><span class="bad">Feed unavailable</span></div>'
        else:
            country_cls = _pct_cls(stats.get("country_pct"))
            city_cls = _pct_cls(stats.get("city_pct"))
            routed = stats.get("routed", 0)
            unrouted = stats.get("unrouted", 0)
            too_specific = stats.get("too_specific", 0)
            locode_errors = stats.get("locode_errors", 0)
            route_cls = "good" if unrouted == 0 else ("warn" if unrouted / (routed + unrouted) < 0.10 else "bad")
            unrouted_pct = f" ({unrouted / (routed + unrouted) * 100:.1f}%)" if unrouted else ""
            locode_cls = "good" if locode_errors == 0 else "warn"
            rfc9092 = stats.get("rfc9092", 0)
            rfc9092_str = f' / <b>{rfc9092:,} Geofeed in RIR</b>' if rfc9092 else ''
            stats_html = f"""<div class="card-stats">
  <span>{total:,} prefixes</span>
  <span>Country: <b class="{country_cls}">{country_pct}</b> &nbsp; City: <b class="{city_cls}">{city_pct}</b></span>
  <span>Routing: <b class="{route_cls}">{routed:,} visible</b>{f' / <b class="{route_cls}">{unrouted:,} not visible{unrouted_pct}</b>' if unrouted else ''}{f' / {too_specific:,} too specific' if too_specific else ''}</span>
  <span>Location names: <b class="{locode_cls}">{locode_errors:,} issue{'s' if locode_errors != 1 else ''}</b>{rfc9092_str}</span>
</div>"""
        cards.append(
            f'<a class="feed-card" href="{href}"><div class="feed-logo">{logo_html}</div>'
            f'<div class="feed-title">{feed["title"]}</div>{stats_html}</a>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Geofeed Monitor</title>
<link rel="icon" href="{GLOBE_FAVICON}">
<style>
  :root {{ --squid-ink: #232f3e; --squid-ink-light: #37475a; --text-primary: #16191f; --text-secondary: #545b64; --bg-page: #f2f3f3; --bg-card: #ffffff; --border: #d5dbdb; --aws-orange: #ff9900; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg-page); color: var(--text-primary); line-height: 1.5; min-height: 100vh; display: flex; flex-direction: column; }}
  .topbar {{ background: var(--squid-ink); padding: 12px 32px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.15); }}
  .topbar svg {{ height: 40px; width: auto; }}
  .topbar h1 {{ color: #fff; font-size: 20px; font-weight: 700; }}
  .topbar .separator {{ width: 1px; height: 28px; background: var(--squid-ink-light); }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 48px 32px; flex: 1; display: flex; flex-direction: column; align-items: center; gap: 16px; }}
  .container h2 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
  .container p {{ font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; text-align: center; max-width: 600px; }}
  .feed-grid {{ display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; }}
  .feed-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 32px 40px; display: flex; flex-direction: column; align-items: center; gap: 16px; text-decoration: none; color: var(--text-primary); transition: box-shadow 0.2s, border-color 0.2s; width: 260px; }}
  .feed-card:hover {{ border-color: var(--aws-orange); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
  .feed-logo {{ height: 60px; display: flex; align-items: center; }}
  .feed-logo svg {{ height: 50px; }}
  .feed-logo img {{ height: 60px; }}
  .feed-title {{ font-size: 14px; font-weight: 600; text-align: center; }}
  .card-stats {{ display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 11px; color: var(--text-secondary); border-top: 1px solid var(--border); padding-top: 10px; width: 100%; text-align: center; }}
  .card-stats .good {{ color: #037f0c; }}
  .card-stats .warn {{ color: #8a6d00; }}
  .card-stats .bad {{ color: #d13212; }}
  footer {{ text-align: center; padding: 16px; font-size: 12px; color: #545b64; }}
</style>
</head>
<body>
<div class="topbar">
  {GLOBE_SVG}
  <div class="separator"></div>
  <h1>Geofeed Monitor</h1>
</div>
<div class="container">
  <h2>Select a Geofeed Report</h2>
  <p>Monitors the accuracy of RFC 8805 geofeeds by validating geolocation claims against third-party databases.</p>
  <div class="feed-grid">{''.join(cards)}</div>
</div>
<footer>Last updated: {now_utc}</footer>
</body></html>"""
    Path("./index.html").write_text(html, encoding="utf-8")
    print("Landing page written to index.html")
