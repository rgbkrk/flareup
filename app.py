#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import time

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
                 drain_domain="nbviewer-drain.ipython.org",
                 status_page=None):

        self.cloud_flare = CloudFlare(cloudflare_email, cloudflare_api_key)
        self.main_domain = main_domain
        self.drain_domain = drain_domain

        self.zone = Zone(self.cloud_flare, zone)

        self.http_client = AsyncHTTPClient()

        self.status_page = status_page


    @gen.coroutine
    def health_check(self):
        app_log.info("Performing Health Check!")
        main_records = yield self.zone.list_dns_records(self.main_domain)
        drain_records = yield self.zone.list_dns_records(self.drain_domain)

        app_log.info("{} in main, {} in drain".format(len(main_records), len(drain_records)))

        to_drain = []
        to_main = []

        totals = 0.0

        for record in main_records:
            try:
                ip = record['content']
                resp = yield self.http_client.fetch(ip)
                app_log.debug(resp)

                # Total is in seconds, convert to ms
                totals += resp.time_info['total']*1000

            except HTTPError as e:
                app_log.error(e)
                
        # Log to statuspage
        if self.status_page is not None:
            average_response = ( totals/len(main_records) )
            self.status_page.report(time.time(), average_response)
            app_log.info("Average Response: {} ms".format(average_response))

class StatusPage():

    api_url = "https://api.statuspage.io"
    def __init__(self, api_key, page_id, metric_id):
        self.api_key = api_key
        self.page_id = page_id

        # TODO: Make this generic since we could report multiple metrics
        self.default_metric_id = metric_id

        self.default_headers = {
            "Content-Type":"application/json",
            "Authorization": "OAuth {}".format(self.api_key)
        }

        self.async_http_client = AsyncHTTPClient(force_instance=True,
                                                 defaults=dict(user_agent="rgbkrk/flareup"))

    def report(self, timestamp, value, metric_id=None):
        if metric_id is None:
            metric_id = self.default_metric_id

        endpoint = (self.api_url + "/v1/pages/{}/metrics/{}/data.json").format(
                    self.page_id, metric_id)

        resp = requests.post(endpoint, headers=self.default_headers,
                            json={'data':{'timestamp':timestamp, 'value':value}})

        app_log.debug(resp.content)

def main(health_check_secs=60):
    cloudflare_email = os.environ["CLOUDFLARE_EMAIL"]
    cloudflare_api_key = os.environ["CLOUDFLARE_API_KEY"]

    status_page_api_key = os.environ["STATUS_PAGE_API_KEY"]
    status_page_page_id = os.environ["STATUS_PAGE_PAGE_ID"]
    status_page_metric_id = os.environ["STATUS_PAGE_METRIC_ID"]

    status_page = StatusPage(status_page_api_key, status_page_page_id, status_page_metric_id)

    cf = FlareWatch(cloudflare_email, cloudflare_api_key,
                    status_page=status_page)

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
