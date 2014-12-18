#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import requests

import tornado
from tornado import gen, ioloop
from tornado.log import app_log
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
from tornado.httputil import url_concat


AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

class FlareWatch():
    cloudflare_api_url = "https://api.cloudflare.com/client/v4"

    def __init__(self, cloudflare_email, cloudflare_api_key,
                 zone="ipython.org",
                 domain="nbviewer.ipython.org"):
        self.cloudflare_email = cloudflare_email
        self.cloudflare_api_key = cloudflare_api_key

        self.zone = zone
        self.domain = domain

        self.default_headers = {
            "X-Auth-Key": cloudflare_api_key,
            "X-Auth-Email": cloudflare_email,
        }

        # Ensure we have the zone ID first
        self.zone_id = self.acquire_zone_id()
        app_log.info("Acquire zone ID {} for domain {}".format(self.zone_id,
            self.domain))

    def acquire_zone_id(self):
        zones_resp = requests.get(self.cloudflare_api_url + "/zones",
                headers=self.default_headers).json()
        zones = zones_resp['result']
        named_zones = {zone['name']: zone['id'] for zone in zones}
        zone_id = named_zones[self.zone]
        return zone_id

    def list_dns_records(self):
        url = self.cloudflare_api_url + "/zones/{}/dns_records".format(self.zone_id)
        records_resp = requests.get(url, params=dict(type="A", name=self.domain),
                                    headers=self.default_headers).json()
        records = records_resp['result']

        assert set([record['name'] for record in records]) == set([self.domain])

        return records




def main():
    cloudflare_email = os.environ["CLOUDFLARE_EMAIL"]
    cloudflare_api_key = os.environ["CLOUDFLARE_API_KEY"]
    cloudflare_api_url = "https://api.cloudflare.com/client/v4"

    cf = FlareWatch(cloudflare_email, cloudflare_api_key)

    records = cf.list_dns_records()

    for record in records:
        print(record)
        print(record['content'])
        print(record['id'])
        #url = cloudflare_api_url + "/zones/{}/dns_records/{}".format(zone_id, record_id)
        #records_resp = requests.get(url, params=dict(type="A", name=domain),
        #                            headers=headers).json()

if __name__ == "__main__":
    main()
