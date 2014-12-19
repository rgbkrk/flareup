flareup
=======

Adjust hosts according to solar flares.


```console
docker run --name flareup \
           -e CLOUDFLARE_EMAIL=projectjupyter@gmail.com \
           -e CLOUDFLARE_API_KEY=<cloud_flare_api_key> \
           -e STATUS_PAGE_API_KEY=<status_page_api_key> \
           -e STATUS_PAGE_PAGE_ID=fzcq6v7wcg65 \
           -e ACTIVE_NODES_METRIC_ID=h0hdq19vhgsb \
           -e UNRESPONSIVE_NODES_METRIC_ID=qhj4s5fj1n5n \
           -e AVERAGE_RESPONSE_METRIC_ID=pxzhrhl9167z \
           -e MAX_RESPONSE_METRIC_ID=slzkt46pg965 \
           -e MIN_RESPONSE_METRIC_ID=08m63jpkf0km \
           rgbkrk/flareup
```


### Roadmap

* [X] Check status of nodes behind nbviewer.ipython.org
* [X] Report response times to statuspage.io
* [ ] For "lost" nodes, take them off of nbviewer.ipython.org and set to nbviewer-drain.ipython.org
* [ ] Detect nodes that are back from nbviewer-drain.ipython.org and add them back to nbviewer.ipython.org
