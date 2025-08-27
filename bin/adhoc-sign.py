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
        f"/releases/download/{release}/mozregression-gui-unsigned.exe",
    }

    operating_systems = {
        "macOS": ["macapp"],
        "windows": ["gcp_prod_autograph_authenticode_202412"],
    }

    params = {}

    os = args.os
    signing_formats = operating_systems[os]

    url = urls[os]
    response = requests.get(url)
    if response.status_code != 200:
        response.raise_for_status()

    params[os] = {
        "artifact-name": url.split("/")[-1],
        "bug": int(args.bug),
        "fetch": {"url": url},
        "filesize": len(response.content),
        "private-artifact": False,
        "product": "mozregression",
        "reason": f"Sign application bundle for mozregression {release}.",
        "requestor": args.requestor,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "signing-formats": signing_formats,
    }

    if os == "macOS":
        params[os]["mac-behavior"] = "mac_sign"
        params[os]["signingscript-notarization"] = True

    print(yaml.dump_all(params.values()))


def create_parser():
    parser = argparse.ArgumentParser(description="print ad-hoc signing manifest")
    parser.add_argument("release", nargs=1, help="signing manifest release tag")
    parser.add_argument("--bug", default="0", help="optional bug number to include")
    parser.add_argument(
        "--os",
        default="macOS",
        help="operating system build to fetch",
        choices=("windows", "macOS"),
    )
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
