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
import argparse
import os
import sys
import imp
import json
import urllib2
import urllib

logger = logging.getLogger(__name__)

conf_path = os.getenv("SSOADMJSON_CONF", "/opt/osstech/etc/openam/ssoadmjson.conf")

am_url = "http://localhost:8080/openam"
am_realm = '/'
am_login_realm = '/'
am_login_user = "amadmin"
am_login_pass = "blah-blah"

## ======================================================================


def main(argv):
    imp.load_source(__name__, conf_path)

    argp = argparse.ArgumentParser(prog=argv[0])
    argp.add_argument(
        'method',
        metavar='METHOD',
        help='HTTP method (get, post, put, delete)',
        type=str,
        choices=('get', 'post', 'put', 'delete', 'login'),
    )
    argp.add_argument(
        'section',
        metavar='SECTION',
        type=str,
        nargs='?',
        default='realms',
    )
    argp.add_argument(
        'name',
        metavar='NAME',
        help='Item name or UUID',
        type=str,
        nargs='?',
        default=None,
    )
    argp.add_argument(
        '--url',
        help='OpenAM server URL',
        type=str,
        default=am_url,
    )
    argp.add_argument(
        '--login-realm',
        help='Realm for login',
        type=str,
        default=am_login_realm,
    )
    argp.add_argument(
        '--realm',
        help='Realm',
        type=str,
        default=am_realm,
    )
    argp.add_argument(
        '--json-indent',
        metavar='N',
        help='Indent level for JSON output (negative value disables pretty-print)',
        type=int,
        default=4,
    )
    argp.add_argument(
        '--no-logout',
        dest='logout',
        action='store_false',
        default=True,
    )
    args = argp.parse_args(argv[1:])

    if args.json_indent < 0:
        args.json_indent = None

    ## FIXME: Raise an exception if name has invalid characters?

    ret = 0
    token = None
    try:
        data, token = am_login(am_url, args.realm, args.login_realm, am_login_user, am_login_pass)
        if args.method == "login":
            pass
        elif args.method == "get":
            res, data = am_get(token, args.section, args.name)
            data = data["result"]
        elif args.method == "post":
            data = json.loads(sys.stdin.read())
            res, data = am_post(token, args.section, args.name, data, action="create")
        elif args.method == "put":
            data = json.loads(sys.stdin.read())
            if args.name is None:
                args.name = data.get('uuid', data.get('name'))
            res, data = am_put(token, args.section, args.name, data)
        elif args.method == "delete":
            res, data = am_delete(token, args.section, args.name)
        else:
            logger.error("Unknown method: %s", args.method)
            return 1
    except urllib2.HTTPError as e:
        data = json.loads(e.read())
        code = e.getcode()
        ## Map an error HTTP response code (4XX, 5XX) into the exit code
        ret = code - 350
        ## code = ret + 350

    print(json.dumps(data, indent=args.json_indent, sort_keys=True))

    if args.logout and token is not None:
        am_logout(token)

    return ret


def am_login(url, realm, login_realm, login_user, login_pass):
    token = {
        "url": url,
        "url_json": url + '/json/',
        "url_realm": urllib.quote(realm),
        "url_login_realm": urllib.quote(login_realm),
        "realm": realm,
        "login_realm": login_realm,
        "login_user": login_user,
        "headers": {
            "Content-Type": "application/json",
        },
    }
    headers = {
        "X-OpenAM-Username": login_user,
        "X-OpenAM-Password": login_pass,
    }

    res, data = am_post(token, "authenticate", None, {}, headers=headers)

    token["headers"].update({"iPlanetDirectoryPro": data["tokenId"]})

    return data, token


def am_logout(token):
    res, data = am_post(token, "sessions", None, {}, action="logout")


def am_url_and_headers(token, section, name=None, headers={}):
    url = token["url_json"] + urllib.quote(section, safe="")
    if name is not None:
        url += '/' + urllib.quote(name, safe="")
    url += '?realm=' + token["url_login_realm"]
    headers = dict(headers, **token["headers"])

    return (url, headers)


def am_get(token, section, name, data={}, headers={}):
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


def am_post(token, section, name, data, headers={}, action=None):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if action is not None:
        url += '&_action=' + urllib.quote(action)

    req = urllib2.Request(url, json.dumps(data), headers)
    res = urllib2.urlopen(req)
    data = json.loads(res.read())

    return (res, data)


def am_put(token, section, name, data, headers={}, action=None):
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

    sys.exit(main(sys.argv))
