#! /usr/bin/env python

import argparse
import hashlib

import yaml
import requests


def main(args: argparse.Namespace):
    release = args.release[0]
    filename = "mozregression-gui-app-bundle.tar.gz"
    urls = {
        "macOS": "https://github.com/mozilla/mozregression"
        f"/releases/download/{release}/{filename}",
        "windows": "https://github.com/mozilla/mozregression"
        f"/releases/download/{release}/mozregression-gui.exe",
    }

    operating_systems = {
        "macOS": ["macapp"],
    }

    params = {}

    for os, signing_formats in operating_systems.items():
        url = urls[os]
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Could not fetch {url} ({response.status_code})")

        params[os] = {}
        params[os]["artifact-name"] = url.split("/")[-1]
        params[os]["bug"] = int(args.bug)
        params[os]["fetch"] = {"url": url}
        params[os]["filesize"] = len(response.content)
        params[os]["private-artifact"] = False
        params[os]["product"] = "mozregression"
        params[os]["reason"] = f"Sign application bundle for mozregression {release}."
        params[os]["requestor"] = args.requestor
        params[os]["sha256"] = hashlib.sha256(response.content).hexdigest()
        params[os]["signing-formats"] = signing_formats
        params[os]["signingscript-notarization"] = True
        if os == "macOS":
            params[os]["mac-behavior"] = "mac_sign"

    print(yaml.dump_all(params.values()))


def create_parser():
    parser = argparse.ArgumentParser(description="print ad-hoc signing manifest")
    parser.add_argument("release", nargs=1, help="signing manifest release tag")
    parser.add_argument("--bug", default="0", help="optional bug number to include")
    parser.add_argument(
        "--requestor",
        default="Zeid Zabaneh <zeid@mozilla.com>",
        help="the person who is requesting the signing",
    )
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    main(args)
