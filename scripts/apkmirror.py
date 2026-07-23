#!/usr/bin/env python3
"""Small, independent APKMirror client used by MorpheModule.

APKMirror is a best-effort source. Cloudflare challenges are reported to the
caller immediately so the builder can continue with its next configured source.
"""

import argparse
import os
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.apkmirror.com"
USER_AGENT = "MorpheModule/1.0 (+https://github.com/KimPig/MorpheModule)"
REQUEST_INTERVAL_SECONDS = 3.0


class APKMirrorError(RuntimeError):
    pass


class Client:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/zip;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
            }
        )
        self.last_request_at = 0.0

    @staticmethod
    def validate_url(url: str, *, allow_storage: bool = False) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        is_apkmirror = (
            hostname == "apkmirror.com" or hostname.endswith(".apkmirror.com")
        )
        is_storage = allow_storage and hostname.endswith(".r2.cloudflarestorage.com")
        if parsed.scheme != "https" or not (is_apkmirror or is_storage):
            raise APKMirrorError(f"Refusing non-APKMirror URL: {url}")
        return url

    def request(
        self,
        url: str,
        *,
        referer: str | None = None,
        stream: bool = False,
        allow_storage: bool = False,
    ):
        self.validate_url(url)
        delay = REQUEST_INTERVAL_SECONDS - (time.monotonic() - self.last_request_at)
        if delay > 0:
            time.sleep(delay)

        headers = {"Referer": referer} if referer else None
        try:
            response = self.session.get(
                url,
                headers=headers,
                stream=stream,
                timeout=(15, 90),
                allow_redirects=True,
            )
        except requests.RequestException as error:
            raise APKMirrorError(f"Request failed: {url}: {error}") from error
        finally:
            self.last_request_at = time.monotonic()

        self.validate_url(response.url, allow_storage=allow_storage)
        if response.headers.get("cf-mitigated", "").lower() == "challenge":
            response.close()
            raise APKMirrorError(f"Cloudflare challenge received: {url}")
        if response.status_code != 200:
            status = response.status_code
            response.close()
            raise APKMirrorError(f"HTTP {status}: {url}")
        return response

    def html(self, url: str, *, referer: str | None = None) -> BeautifulSoup:
        with self.request(url, referer=referer) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "html" not in content_type:
                raise APKMirrorError(
                    f"Expected HTML but received {content_type!r}: {url}"
                )
            return BeautifulSoup(response.content, "html.parser")

    def bytes(self, url: str) -> bytes:
        with self.request(url) as response:
            return response.content


def normalized_architecture(architecture: str) -> str:
    return "armeabi-v7a" if architecture == "arm-v7a" else architecture


def variant_matches(row, architecture: str, dpi: str) -> bool:
    text = " ".join(row.stripped_strings).lower()
    wanted_arch = normalized_architecture(architecture).lower()
    architecture_ok = (
        architecture == "all"
        or "universal" in text
        or "noarch" in text
        or wanted_arch in text
        or (
            wanted_arch == "arm64-v8a"
            and "arm64-v8a + armeabi-v7a" in text
        )
    )
    if not architecture_ok:
        return False

    if not dpi:
        return True
    accepted_dpi = {"nodpi", "anydpi", *dpi.lower().split()}
    return any(value in text for value in accepted_dpi)


def choose_variant(version_page: BeautifulSoup, architecture: str, dpi: str):
    table = version_page.find("div", class_="table")
    if table is None:
        if version_page.select_one("a.downloadButton[href]"):
            return False, None
        raise APKMirrorError("Variant table not found")

    candidates: list[tuple[bool, str]] = []
    for row in table.find_all("div", recursive=False)[1:]:
        link = row.select_one("a.accent_color[href]")
        if link is None or not variant_matches(row, architecture, dpi):
            continue
        badge = row.find("span", class_="apkm-badge")
        is_bundle = bool(
            badge is not None and badge.get_text(strip=True).upper() == "BUNDLE"
        )
        candidates.append((is_bundle, urljoin(BASE_URL, link["href"])))

    if not candidates:
        raise APKMirrorError(
            f"No variant matches architecture={architecture!r}, dpi={dpi!r}"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0]


def resolve_download(client: Client, version_url: str, architecture: str, dpi: str):
    version_page = client.html(version_url)
    is_bundle, variant_url = choose_variant(version_page, architecture, dpi)
    if variant_url is None:
        variant_page = version_page
        variant_referer = version_url
    else:
        variant_page = client.html(variant_url, referer=version_url)
        variant_referer = variant_url

    button = variant_page.select_one("a.downloadButton[href]")
    if button is None:
        raise APKMirrorError("Download button not found")
    landing_url = urljoin(BASE_URL, button["href"])
    landing_page = client.html(landing_url, referer=variant_referer)

    links = landing_page.select('a[rel~="nofollow"][href]')
    if not links:
        raise APKMirrorError("Final download link not found")
    preferred = next(
        (link for link in links if "download.php" in link.get("href", "")),
        links[0],
    )
    download_url = client.validate_url(urljoin(BASE_URL, preferred["href"]))
    return is_bundle, download_url, landing_url


def download_archive(
    client: Client,
    url: str,
    output: Path,
    *,
    referer: str,
    is_bundle: bool,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(f".{output.name}.part")
    partial.unlink(missing_ok=True)
    try:
        with client.request(
            url,
            referer=referer,
            stream=True,
            allow_storage=True,
        ) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise APKMirrorError("Download endpoint returned HTML")
            with partial.open("wb") as destination:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        destination.write(chunk)

        if not zipfile.is_zipfile(partial):
            raise APKMirrorError("Downloaded file is not a valid ZIP/APK archive")
        if is_bundle:
            with zipfile.ZipFile(partial) as archive:
                if not any(name.lower().endswith(".apk") for name in archive.namelist()):
                    raise APKMirrorError("Downloaded bundle contains no APK entries")
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)


def command_get(args) -> None:
    sys.stdout.buffer.write(Client().bytes(args.url))


def command_download(args) -> None:
    client = Client()
    is_bundle, download_url, referer = resolve_download(
        client, args.url, args.arch, args.dpi
    )
    output = Path(f"{args.output}.apkm" if is_bundle else args.output)
    download_archive(
        client,
        download_url,
        output,
        referer=referer,
        is_bundle=is_bundle,
    )
    print(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    get_parser = commands.add_parser("get")
    get_parser.add_argument("url")
    get_parser.set_defaults(func=command_get)

    download_parser = commands.add_parser("download")
    download_parser.add_argument("url")
    download_parser.add_argument("output")
    download_parser.add_argument("--arch", default="all")
    download_parser.add_argument("--dpi", default="")
    download_parser.set_defaults(func=command_download)

    args = parser.parse_args()
    try:
        args.func(args)
    except (APKMirrorError, OSError, zipfile.BadZipFile) as error:
        print(f"apkmirror.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
