#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup


BASE_URL = "https://www.apkmirror.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def scraper():
    session = cloudscraper.create_scraper()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def request(session, url, *, stream=False, headers=None):
    response = session.get(url, stream=stream, headers=headers, timeout=60)
    if (
        response.status_code != 200
        or response.headers.get("cf-mitigated") == "challenge"
    ):
        response.close()
        raise RuntimeError(
            f"APKMirror request failed ({response.status_code}, "
            f"cf-mitigated={response.headers.get('cf-mitigated')}): {url}"
        )
    return response


def page(session, url):
    with request(session, url) as response:
        return BeautifulSoup(response.content, "html.parser")


def normalize_arch(arch):
    if arch == "arm-v7a":
        return "armeabi-v7a"
    return arch


def matches_variant(row, arch, dpi):
    text = " ".join(row.stripped_strings).lower()
    normalized_arch = normalize_arch(arch).lower()

    arch_matches = (
        arch == "all"
        or "universal" in text
        or "noarch" in text
        or normalized_arch in text
        or (
            normalized_arch == "arm64-v8a"
            and "arm64-v8a + armeabi-v7a" in text
        )
    )
    if not arch_matches:
        return False

    if not dpi:
        return True

    accepted_dpis = {"nodpi", "anydpi", *dpi.lower().split()}
    return any(value in text for value in accepted_dpis)


def find_variant(version_page, arch, dpi):
    variants_table = version_page.find("div", {"class": "table"})
    if variants_table is None:
        # Some APKMirror version URLs directly display the download page.
        if version_page.find("a", {"class": "downloadButton"}):
            return False, None
        raise RuntimeError("APKMirror variants table was not found")

    rows = variants_table.find_all("div", recursive=False)[1:]
    candidates = []
    for row in rows:
        link = row.find("a", {"class": "accent_color"})
        if link is None or not link.get("href") or not matches_variant(row, arch, dpi):
            continue
        badge = row.find("span", {"class": "apkm-badge"})
        is_bundle = bool(
            badge is not None and badge.get_text(strip=True).upper() == "BUNDLE"
        )
        candidates.append((is_bundle, urljoin(BASE_URL, link["href"])))

    if not candidates:
        raise RuntimeError(
            f"No APKMirror variant matched arch={arch!r}, dpi={dpi!r}"
        )

    # Preserve the builder's existing preference for a standalone APK.
    candidates.sort(key=lambda candidate: candidate[0])
    return candidates[0]


def find_download_url(session, variant_url, version_page):
    variant_page = version_page if variant_url is None else page(session, variant_url)
    button = variant_page.find("a", {"class": "downloadButton"})
    if button is None or not button.get("href"):
        raise RuntimeError("APKMirror download button was not found")

    download_page_url = urljoin(BASE_URL, button["href"])
    download_page = page(session, download_page_url)
    direct_link = download_page.find("a", {"rel": "nofollow"})
    if direct_link is None or not direct_link.get("href"):
        raise RuntimeError("APKMirror final download link was not found")

    return urljoin(BASE_URL, direct_link["href"]), download_page_url


def download(session, url, output, referer):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"tmp.{output.name}")
    temporary.unlink(missing_ok=True)

    try:
        with request(
            session,
            url,
            stream=True,
            headers={"Referer": referer},
        ) as response:
            with temporary.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def command_get(args):
    session = scraper()
    with request(session, args.url) as response:
        sys.stdout.buffer.write(response.content)


def command_download(args):
    session = scraper()
    version_page = page(session, args.url)
    is_bundle, variant_url = find_variant(version_page, args.arch, args.dpi)
    download_url, referer = find_download_url(session, variant_url, version_page)
    output = Path(f"{args.output}.apkm" if is_bundle else args.output)
    download(session, download_url, output, referer)
    print(output)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("url")
    get_parser.set_defaults(func=command_get)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("url")
    download_parser.add_argument("output")
    download_parser.add_argument("--arch", default="all")
    download_parser.add_argument("--dpi", default="")
    download_parser.set_defaults(func=command_download)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as error:
        print(f"apkmirror.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
