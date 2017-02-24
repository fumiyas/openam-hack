#!/usr/bin/python
## -*- encoding: utf-8 -*- vim:shiftwidth=4
##
## OpenAM: Administration tool by JSON data via ForgeRock Common REST API
## Copyright (c) 2017 SATOH Fumiyasu @ OSS Technology Corp., Japan
##
## License: GNU General Public License version 3
##

from __future__ import print_function

import logging
import os
import sys
import imp
import json
import urllib2
import urllib

logger = logging.getLogger(__name__)

conf_path = os.getenv("SSOADMJSON_CONF", "/opt/osstech/etc/openam/ssoadmjson.conf")

am_url = "http://localhost:8080/openam"
am_user = "amadmin"
am_pass = "blah-blah"

## ======================================================================


def main(argv):
    ret = 0

    realm = argv.pop(0)
    section = argv.pop(0)
    method = argv.pop(0)
    name = argv.pop(0) if len(argv) else None

    ## FIXME: Raise an exception if name has invalid characters?

    imp.load_source(__name__, conf_path)

    token = am_login(am_url, realm, am_user, am_pass)

    try:
        if method == "get":
            res, data = am_get(token, section, name)
            data = data["result"]
        elif method == "post":
            data = json.loads(sys.stdin.read())
            res, data = am_post(token, section, name, data, action="create")
        elif method == "put":
            data = json.loads(sys.stdin.read())
            res, data = am_put(token, section, name)
        elif method == "delete":
            res, data = am_delete(token, section, name)
        else:
            logger.error("Unknown method: %s", method)
            return 1
    except urllib2.HTTPError as e:
        data = json.loads(e.read())
        code = e.getcode()
        ## Map an error HTTP response code (4XX, 5XX) into the exit code
        ret = code - 350
        ## code = ret + 350

    print(json.dumps(data, indent=4, sort_keys=True))

    am_logout(token)

    return ret


def am_login(url, realm, user, pw):
    token = {
        "url": url,
        "url_json": url + '/json/',
        "url_realm": urllib.quote(realm),
        "realm": realm,
        "user": user,
        "headers": {
            "Content-Type": "application/json",
        },
    }
    headers = {
        "X-OpenAM-Username": user,
        "X-OpenAM-Password": pw,
    }

    res, data = am_post(token, "authenticate", headers=headers)

    token["headers"].update({"iPlanetDirectoryPro": data["tokenId"]})

    return token


def am_logout(token):
    res, data = am_post(token, "sessions", action="logout")


def am_url_and_headers(token, section, name=None, headers={}):
    url = token["url_json"] + urllib.quote(section, safe="")
    if name is not None:
        url += '/' + urllib.quote(name, safe="")
    url += '?realm=' + token["url_realm"]
    headers = dict(headers, **token["headers"])

    return (url, headers)


def am_get(token, section, name=None, data={}, headers={}):
    url, headers = am_url_and_headers(token, section, headers=headers)
    if name is None:
        data["_queryFilter"] = "true"
    else:
        data["_queryFilter"] = 'name eq "%s"' % name
    url += '&' + urllib.urlencode(data)

    req = urllib2.Request(url, None, headers)
    res = urllib2.urlopen(req)
    data = json.loads(res.read())

    return (res, data)


def am_post(token, section, name=None, data={}, headers={}, action=None):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if action is not None:
        url += '&_action=' + urllib.quote(action)

    req = urllib2.Request(url, json.dumps(data), headers)
    res = urllib2.urlopen(req)
    data = json.loads(res.read())

    return (res, data)


def am_put(token, section, name, data={}, headers={}, action=None):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if action is not None:
        url += '&_action=' + urllib.quote(action)

    req = urllib2.Request(url, json.dumps(data), headers)
    req.get_method = lambda: 'PUT'
    res = urllib2.urlopen(req)
    data = json.loads(res.read())

    return (res, data)


def am_delete(token, section, name, data={}, headers={}):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    url += '&' + urllib.urlencode(data)

    req = urllib2.Request(url, None, headers)
    req.get_method = lambda: 'DELETE'
    res = urllib2.urlopen(req)
    data = json.loads(res.read())

    return (res, data)


## ======================================================================

if __name__ == '__main__':
    logformatter = logging.Formatter('%(filename)s: %(levelname)s: %(message)s')
    loghandler = logging.StreamHandler()
    loghandler.setFormatter(logformatter)
    logger.addHandler(loghandler)

    if len(sys.argv) < 3:
        print("Usage: %s REALM SECTION METHOD [NAME_OR_UUID]" % (sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    sys.exit(main(sys.argv[1:]))
