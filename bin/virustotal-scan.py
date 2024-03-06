#! /usr/bin/env python

import argparse
import requests
from time import sleep
import sys


class APIWrapper:
    def __init__(self, apikey):
        self.headers = {
            "accept": "application/json",
            "x-apikey": apikey,
        }

    def get(self, path):
        return requests.get(path, headers=self.headers)

    def post(self, path, **kwargs):
        return requests.post(path, headers=self.headers, **kwargs)


def main(args: argparse.Namespace):
    api = APIWrapper(args.apikey[0])
    base_url = "https://www.virustotal.com/api/v3"

    file_upload_url_response = api.get(f"{base_url}/files/upload_url")
    file_upload_url = file_upload_url_response.json()["data"]

    files = {
        "file": (
            "mozregression-gui.exe",
            open("./gui/wininst/mozregression-gui.exe", "rb"),
            "application/octet-stream",
        ),
    }

    upload_response = api.post(file_upload_url, files=files)
    analysis_url = upload_response.json()["data"]["links"]["self"]

    while analysis_response := api.get(analysis_url):
        # Sleep for one second to throttle requests to VirusTotal.
        sleep(1)

        if analysis_response.status_code != 200:
            # Analysis endpoint does not exist yet, try again...
            continue

        analysis = analysis_response.json()
        if analysis["data"]["attributes"]["status"].lower() != "completed":
            # Analysis has not completed yet, try again...
            continue
        else:
            break

    stats = analysis["data"]["attributes"]["stats"]
    if stats["malicious"]:
        sys.stdout.write("VirusTotal scan failed.\n")
        for key, value in stats.items():
            sys.stderr.write(f"{key}: {value}\n")
        sys.stdout.write(f"Analysis ID: {analysis['data']['id']}\n")
        sys.exit(1)
    else:
        sys.stdout.write("VirusTotal scan passed.\n")
        sys.stdout.write(f"Analysis ID: {analysis['data']['id']}\n")
        sys.exit()


def create_parser():
    parser = argparse.ArgumentParser(description="send file for VirusTotal scanning")
    parser.add_argument("apikey", nargs=1, help="VirusTotal API Key")
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    main(args)
