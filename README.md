flareup
=======

Adjust hosts according to solar flares


```console
$ docker run -e CLOUDFLARE_EMAIL=projectjupyter@gmail.com \
             -e CLOUDFLARE_API_KEY=<cloud_flare_api_key> \
             -e STATUS_PAGE_API_KEY=<status_page_api_key> \
             -e STATUS_PAGE_PAGE_ID=fzcq6v7wcg65 \
             -e STATUS_PAGE_METRIC_ID=pxzhrhl9167z \
             rgbkrk/flareup
```
