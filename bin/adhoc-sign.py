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

    # Windows signing is not yet supported by adhoc-signing for mozregression.
    signing_formats = {
        # "windows": ["autograph_authenticode"],
        "macOS": ["macapp"],
    }

    params = {}

    for signing_format in signing_formats:
        params[signing_format] = {}
        url = urls[signing_format]
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Could not fetch {url} ({response.status_code})")

        params[signing_format]["artifact-name"] = url.split("/")[-1]
        params[signing_format]["bug"] = int(args.bug)
        params[signing_format]["fetch"] = {"url": url}
        params[signing_format]["filesize"] = len(response.content)
        params[signing_format]["private-artifact"] = False
        params[signing_format]["product"] = "mozregression"
        params[signing_format]["reason"] = f"Sign application bundle for mozregression {release}."
        params[signing_format]["requestor"] = args.requestor
        params[signing_format]["sha256"] = hashlib.sha256(response.content).hexdigest()
        params[signing_format]["signing-formats"] = signing_formats[signing_format]
        params[signing_format]["signingscript-notarization"] = True
        if signing_format == "macOS":
            params[signing_format]["mac-behavior"] = "mac_sign"

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
