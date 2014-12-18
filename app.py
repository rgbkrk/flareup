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

class CloudFlare():
    cloudflare_api_url = "https://api.cloudflare.com/client/v4"

    def __init__(self, email, api_key):
        self.email = email
        self.api_key = api_key

        self.default_headers = {
            "X-Auth-Key": self.api_key,
            "X-Auth-Email": self.email,
        } 

        self.async_http_client = AsyncHTTPClient(force_instance=True,
                                           defaults=dict(user_agent="rgbkrk/flareup"))
                                                

    def fetch(self, request, callback=None, raise_error=True, **kwargs):
        '''Sets up the auth headers as necessary'''
        for default_header in self.default_headers:
            if default_header not in request.headers:
                request.headers[default_header] = self.default_headers[default_header]

        app_log.debug("CloudFlare API request: {}".format(request))

        return self.async_http_client.fetch(request, callback=callback,
                                            raise_error=raise_error,
                                            kwargs=kwargs)

class Zone():
    def __init__(self, cloud_flare, zone="ipython.org"):
        self.cf = cloud_flare
        self.zone = zone

        self.zone_id = self.acquire_zone_id()
        app_log.info("Acquired zone ID {} for {}".format(self.zone_id, zone))

    def acquire_zone_id(self):
        zones_resp = requests.get(self.cf.cloudflare_api_url + "/zones",
                                  headers=self.cf.default_headers).json()

        app_log.debug(zones_resp)
        zones = zones_resp['result']
        named_zones = {zone['name']: zone['id'] for zone in zones}
        zone_id = named_zones[self.zone]
        return zone_id

    @gen.coroutine
    def list_dns_records(self, domain):
        url = self.cf.cloudflare_api_url + "/zones/{}/dns_records".format(self.zone_id)

        full_url = url_concat(url, dict(type="A", name=domain))

        req = HTTPRequest(full_url)

        resp = yield self.cf.fetch(req)

        dns_response = json.loads(resp.body.decode('utf8', 'replace'))

        records = dns_response['result']

        assert (set([record['name'] for record in records]) == set([domain]))

        return records

class FlareWatch():

    def __init__(self, cloudflare_email, cloudflare_api_key,
                 zone="ipython.org",
                 main_domain="nbviewer.ipython.org",
                 drain_domain="nbviewer-drain.ipython.org"):

        self.cloud_flare = CloudFlare(cloudflare_email, cloudflare_api_key)
        self.main_domain = main_domain
        self.drain_domain = drain_domain

        self.zone = Zone(self.cloud_flare, zone)

        self.http_client = AsyncHTTPClient()


    @gen.coroutine
    def health_check(self):
        app_log.info("Performing Health Check!")
        main_records = yield self.zone.list_dns_records(self.main_domain)
        drain_records = yield self.zone.list_dns_records(self.drain_domain)

        to_drain = []
        to_main = []

        for record in main_records:
            try:
                ip = record['content']
                resp = yield self.http_client.fetch(ip)
                app_log.debug(resp)
            except HTTPError as e:
                # HTTPError is raised for non-200 responses; the response
                # can be found in e.response.
                app_log.error(e)


def main(health_check_secs=60):
    cloudflare_email = os.environ["CLOUDFLARE_EMAIL"]
    cloudflare_api_key = os.environ["CLOUDFLARE_API_KEY"]

    cf = FlareWatch(cloudflare_email, cloudflare_api_key)

    app_log.info("Go time")
    io_loop = ioloop.IOLoop.instance()

    io_loop.add_callback(cf.health_check)

    health_check = ioloop.PeriodicCallback(cf.health_check, 1000*health_check_secs, io_loop=io_loop) #1000*30/10)#, io_loop=io_loop)
    health_check.start()

    io_loop.start()

    app_log.info("All set and ready supposedly")

if __name__ == "__main__":
    tornado.options.parse_command_line()
    main()
