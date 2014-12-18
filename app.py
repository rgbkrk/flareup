#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

import requests

import tornado
import tornado.options
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

        self.http_client = AsyncHTTPClient()

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

    @gen.coroutine
    def list_dns_records(self):
        url = self.cloudflare_api_url + "/zones/{}/dns_records".format(self.zone_id)

        full_url = url_concat(url, dict(type="A", name=self.domain))

        req = HTTPRequest(full_url,
                          method="GET",
                          headers=self.default_headers,
        )

        resp = yield self.http_client.fetch(req)

        dns_response = json.loads(resp.body.decode('utf8', 'replace'))

        records = dns_response['result']
        app_log.info(records)

        assert (set([record['name'] for record in records]) == set([self.domain]))

        yield records

    @gen.coroutine
    def health_check(self):
        app_log.info("Performing Health Check!")
        #records = yield self.list_dns_records()
        

        #responses = yield [self.http_client.fetch(record['content']) for record in records]
        # record['id']

        #app_log.info(responses)


def main():
    cloudflare_email = os.environ["CLOUDFLARE_EMAIL"]
    cloudflare_api_key = os.environ["CLOUDFLARE_API_KEY"]
    cloudflare_api_url = "https://api.cloudflare.com/client/v4"

    cf = FlareWatch(cloudflare_email, cloudflare_api_key)

    app_log.info("Go time")
    io_loop = ioloop.IOLoop.instance()

    io_loop.add_callback(cf.health_check)

    io_loop.start()
    health_check = ioloop.PeriodicCallback(cf.health_check, 1000*30, io_loop=io_loop)
    health_check.start()

    app_log.info("All set and ready supposedly")

if __name__ == "__main__":
    tornado.options.parse_command_line()
    main()
