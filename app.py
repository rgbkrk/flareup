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

        total = 0.0
        response_times = []

        for record in main_records:
            try:
                ip = record['content']
                resp = yield self.http_client.fetch(ip)
                app_log.debug(resp)

                # Total is in seconds, convert to ms
                record_total = resp.time_info['total']*1000
                total += record_total
                response_times.append(record_total)

            except HTTPError as e:
                app_log.error(e)
                to_drain.append(ip)
                
        # Log to statuspage
        if self.status_page is not None:
            average_response = ( total/len(main_records) )
            app_log.info("Average Response: {} ms".format(average_response))

            self.status_page.report(average_response, 
                                    metric_id=self.status_page.metric_ids['average response'])
            self.status_page.report(len(main_records),
                                    metric_id=self.status_page.metric_ids['active nodes'])
            self.status_page.report(max(response_times),
                                    metric_id=self.status_page.metric_ids['max response'])
            self.status_page.report(min(response_times),
                                    metric_id=self.status_page.metric_ids['min response'])
            self.status_page.report(len(to_drain),
                                    metric_id=self.status_page.metric_ids['unresponsive nodes'])

class StatusPage():

    api_url = "https://api.statuspage.io"
    def __init__(self, api_key, page_id, metric_ids):
        self.api_key = api_key
        self.page_id = page_id
        self.metric_ids = metric_ids

        self.default_headers = {
            "Content-Type":"application/json",
            "Authorization": "OAuth {}".format(self.api_key)
        }

        self.async_http_client = AsyncHTTPClient(force_instance=True,
                                                 defaults=dict(user_agent="rgbkrk/flareup"))

    def report(self, value, metric_id, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

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

    metric_ids = {}
    metric_ids['active nodes'] = os.environ["ACTIVE_NODES_METRIC_ID"]
    metric_ids['unresponsive nodes'] = os.environ["UNRESPONSIVE_NODES_METRIC_ID"]
    metric_ids['average response'] = os.environ["AVERAGE_RESPONSE_METRIC_ID"]
    metric_ids['max response'] = os.environ["MAX_RESPONSE_METRIC_ID"]
    metric_ids['min response'] = os.environ["MIN_RESPONSE_METRIC_ID"]

    status_page = StatusPage(status_page_api_key, status_page_page_id,
                             metric_ids=metric_ids)

    cf = FlareWatch(cloudflare_email, cloudflare_api_key,
                    status_page=status_page)

    app_log.info("Go time")
    io_loop = ioloop.IOLoop.instance()

    io_loop.add_callback(cf.health_check)

    health_check = ioloop.PeriodicCallback(cf.health_check, 1000*health_check_secs, io_loop=io_loop) #1000*30/10)#, io_loop=io_loop)
    health_check.start()

    io_loop.start()

if __name__ == "__main__":
    tornado.options.parse_command_line()
    main()
