import logging
import socket
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.utils import timezone

from .ai_writer import clean_text


logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 15


@dataclass(frozen=True)
class FeedItem:
    title: str
    url: str
    summary: str
    published_at: datetime | None = None


def fetch_feed_xml(url, timeout=DEFAULT_TIMEOUT):
    request = Request(
        url,
        headers={
            "User-Agent": "TheUpMediaBot/1.0 (+https://theupmedia.in/)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _child_text(element, tag_names):
    for tag_name in tag_names:
        child = element.find(tag_name)
        if child is not None and child.text:
            return clean_text(child.text)
    return ""


def _atom_link(element):
    for child in element.findall("{*}link"):
        href = child.attrib.get("href", "").strip()
        rel = child.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href
    return ""


def _published_at(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
        except ValueError:
            return None


def parse_feed_items(xml_bytes, limit=20):
    root = ElementTree.fromstring(xml_bytes)
    items = []

    rss_items = root.findall(".//item")
    atom_entries = root.findall(".//{*}entry")
    nodes = rss_items or atom_entries

    for node in nodes[:limit]:
        title = _child_text(node, ["title", "{*}title"])
        url = _child_text(node, ["link", "{*}link"]) or _atom_link(node)
        summary = _child_text(node, ["description", "{*}summary", "{*}content", "content"])
        published_raw = _child_text(node, ["pubDate", "published", "{*}published", "updated", "{*}updated"])
        if not title or not url:
            continue
        items.append(FeedItem(title=title, url=url, summary=summary, published_at=_published_at(published_raw)))
    return items


def fetch_source_items(source, limit=20, timeout=DEFAULT_TIMEOUT):
    try:
        xml_bytes = fetch_feed_xml(source.rss_url, timeout=timeout)
        return parse_feed_items(xml_bytes, limit=limit), ""
    except (ElementTree.ParseError, HTTPError, URLError, socket.timeout, TimeoutError, OSError) as exc:
        logger.warning("RSS fetch failed for source %s: %s", source.pk, exc)
        return [], str(exc)
