#!/usr/bin/python
## -*- encoding: utf-8 -*- vim:shiftwidth=4
##
## OpenAM: Administration tool by JSON data via ForgeRock Common REST API
## Copyright (c) 2017 SATOH Fumiyasu @ OSS Technology Corp., Japan
##
## License: GNU General Public License version 3
##

## TODO: Verify server certificate
## TODO: Use requests instead of urllib2?

from __future__ import print_function

import logging
import argparse
import os
import sys
import re
import errno
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
am_login_password = ""

uuid_re = re.compile(r'^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$')
attrs_meta = ('createdBy', 'creationDate', 'lastModifiedBy', 'lastModifiedDate')

## ======================================================================


def main(argv):
    try:
        imp.load_source(__name__, conf_path)
    except IOError as e:
        if e.errno not in [errno.ENOENT, errno.EPERM, errno.EACCES]:
            raise

    argp = argparse.ArgumentParser(prog=argv[0])
    argp.add_argument(
        'op',
        metavar='OPERATION',
        help='Operation (create, read, update, delete)',
        type=str,
        choices=('create', 'read', 'update', 'delete', 'login', 'get', 'post', 'put'),
    )
    argp.add_argument(
        'section',
        metavar='SECTION',
        help='Items section (realms, users, groups, agents, applications, resourcetypes, policies, ...)',
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
        '--login-realm', '-R',
        metavar='REALM',
        help='Realm for login',
        type=str,
        default=am_login_realm,
    )
    argp.add_argument(
        '-u', '--login-user',
        metavar='USERNAME',
        help='Username for login',
        type=str,
        default=am_login_user,
    )
    argp.add_argument(
        '--login-password',
        dest='login_pass',
        metavar='PASSWORD',
        help=argparse.SUPPRESS,
        type=str,
        default=am_login_password,
    )
    argp.add_argument(
        '-p', '--login-password-file',
        dest='login_pass_file',
        metavar='FILE',
        help='Password file for login',
        type=str,
        default=None,
    )
    argp.add_argument(
        '-r', '--realm',
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
        '--json-include-meta',
        help='Include meta attributes (createdBy and misc.) in JSON output',
        action='store_true',
        default=False,
    )
    argp.add_argument(
        '--json-filter',
        metavar='FILTER',
        help='Filter for JSON output (jq(1)-like)',
        type=str,
        default=None,
    )
    argp.add_argument(
        '--no-logout',
        dest='logout',
        help=argparse.SUPPRESS,
        action='store_false',
        default=True,
    )
    args = argp.parse_args(argv[1:])

    if args.login_pass_file is not None:
        for line in open(args.login_pass_file):
            args.login_pass = line.rstrip('\n')
            break
    if args.json_indent < 0:
        args.json_indent = None
    filters = []
    if args.json_filter:
        for filter in re.split(r'\.', re.sub(r'^\.', '', args.json_filter, count=1)):
            filters += [filter if re.match(r'\D', filter) else int(filter)]
    else:
        filters = []

    ## FIXME: Raise an exception if name has invalid characters?

    ret = 0
    token = None
    try:
        data, token = am_login(args.url, args.realm, args.login_realm, args.login_user, args.login_pass)
        if args.op in ['login']:
            pass
        elif args.op in ['read', 'get']:
            res, data = am_get(token, args.section, args.name)
            data = data["result"]
        elif args.op in ['create', 'post']:
            data = json.loads(sys.stdin.read())
            res, data = am_post(token, args.section, args.name, data, action="create")
        elif args.op in ['update', 'put']:
            data = json.loads(sys.stdin.read())
            if args.name is None:
                args.name = data.get('uuid', data.get('name'))
            res, data = am_put(token, args.section, args.name, data)
        elif args.op in ['delete']:
            res, data = am_delete(token, args.section, args.name)
        else:
            logger.error("Unknown operation: %s", args.op)
            return 1
    except urllib2.HTTPError as e:
        code = e.getcode()
        ## Map an error HTTP response code (4XX, 5XX) into the exit code
        ret = code - 350
        if code >= 500:
            logger.error("HTTP server error: %s", e)
            return ret
        data = json.loads(e.read())
    except urllib2.URLError as e:
        logger.error("Opening URL failed: %s %s", args.url, e)
        return 1

    if not args.json_include_meta:
        if isinstance(data, list):
            for item in data:
                for attr in attrs_meta:
                    item.pop(attr, None)
        else:
            for attr in attrs_meta:
                data.pop(attr, None)

    for filter in filters:
        data = data[filter]

    print(json.dumps(data, indent=args.json_indent, sort_keys=True))

    if args.logout and token is not None:
        am_logout(token)

    return ret


def am_login(url, realm, login_realm, login_user, login_pass):
    token = {
        "url": url,
        "url_json": url + '/json/',
        "url_realm": urllib.quote(login_realm),
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

    token["url_realm"] = urllib.quote(realm)
    token["headers"].update({"iPlanetDirectoryPro": data["tokenId"]})

    return data, token


def am_logout(token):
    res, data = am_post(token, "sessions", None, {}, action="logout")


def am_url_and_headers(token, section, name=None, headers={}):
    url = token["url_json"] + urllib.quote(section, safe="")
    if name is not None:
        url += '/' + urllib.quote(name, safe="")
    url += '?realm=' + token["url_realm"]
    headers = dict(headers, **token["headers"])

    return (url, headers)


def am_get(token, section, name, data={}, headers={}):
    url, headers = am_url_and_headers(token, section, headers=headers)
    if name is None:
        data["_queryFilter"] = "true"
    else:
        if uuid_re.match(name):
            ## FIXME: This does NOT match any UUIDs. Why?
            data["_queryFilter"] = 'uuid eq "%s"' % name
        else:
            data["_queryFilter"] = 'name eq "%s"' % name
    if len(data):
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
    if len(data):
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
