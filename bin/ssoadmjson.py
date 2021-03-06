#!/usr/bin/python3
## -*- coding: utf-8 -*- vim:shiftwidth=4:expandtab:
##
## OpenAM: Administration tool by JSON data via ForgeRock Common REST API
## Copyright (c) 2017-2020 SATOH Fumiyasu @ OSS Technology Corp., Japan
##
## License: GNU General Public License version 3
##

## TODO: Verify server certificate

from __future__ import print_function

import logging
import argparse
import os
import sys
import re
import errno
import imp
import json
import requests

try:
    ## Python 3
    import http.client as http_client
except ImportError:
    ## Python 2
    import httplib as http_client

try:
    ## Python 3
    import urllib.parse as urllib_parse
except ImportError:
    ## Python 2
    import urllib as urllib_parse

logger = logging.getLogger(__name__)

agent_name = os.path.basename(__file__)
conf_path = os.getenv("SSOADMJSON_CONF", "@OPENAM_SYSCONF_DIR@/ssoadmjson.conf")

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
        sys_dont_write_bytecode_save = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        imp.load_source(__name__, conf_path)
    except IOError as e:
        if e.errno not in [errno.ENOENT, errno.EPERM, errno.EACCES]:
            raise
    finally:
        sys.dont_write_bytecode = sys_dont_write_bytecode_save

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
        help='Item name (or UUID for resourcetypes section)',
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
    stdout_save = sys.stdout

    try:
        ## Redirect http_client.HTTPConnection debug log to stderr
        sys.stdout = sys.stderr
        data, token = am_login(args.url, args.realm, args.login_realm, args.login_user, args.login_pass)
        if args.op in ['login']:
            pass
        elif args.op in ['read', 'get']:
            res, data = am_get(token, args.section, args.name)
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
    finally:
        sys.stdout = stdout_save

    if res.status_code >= 400:
        ## Map an error HTTP response code (4XX, 5XX) into the exit code
        ret = res.status_code - 350
        if res.status_code >= 500:
            logger.error("HTTP server error: %s", res.text)
            return ret
        try:
            data = json.loads(res.text)
        except ValueError as e:
            logger.error("Cannot decode response body as JSON: %s" % res.text)
            raise

    if not args.json_include_meta:
        data = dict_delete_keys_recursive(data, attrs_meta)

    for filter in filters:
        data = data[filter]

    print(json.dumps(data, indent=args.json_indent, sort_keys=True))

    if args.logout and token is not None:
        am_logout(token)

    return ret


def dict_delete_keys_recursive(data, keys):
    if isinstance(data, list):
        data = [dict_delete_keys_recursive(x, keys) for x in data]
    elif isinstance(data, dict):
        for key in keys:
            data.pop(key, None)
        data = {k: dict_delete_keys_recursive(data[k], keys) for k in data}

    return data


def am_login(url, realm, login_realm, login_user, login_pass):
    token = {
        "url": url,
        "url_json": url + '/json/',
        "url_realm": urllib_parse.quote(login_realm),
        "realm": realm,
        "login_realm": login_realm,
        "login_user": login_user,
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": agent_name,
        },
    }
    headers = {
        "X-OpenAM-Username": login_user,
        "X-OpenAM-Password": login_pass,
    }

    res, data = am_post(token, "authenticate", None, {}, headers=headers)

    token["url_realm"] = urllib_parse.quote(realm)
    token["headers"]["iPlanetDirectoryPro"] = data["tokenId"]

    return data, token


def am_logout(token):
    res, data = am_post(token, "sessions", None, {}, action="logout")


def am_url_and_headers(token, section, name=None, headers={}):
    url = token["url_json"] + section
    if name is not None:
        url += '/' + urllib_parse.quote(name, safe="")
    url += '?realm=' + token["url_realm"]
    headers = dict(headers, **token["headers"])

    return (url, headers)


def am_get(token, section, name, data={}, headers={}):
    if name is None:
        ## Get all items
        data["_queryFilter"] = "true"
    elif re.match(r'^\w+ ((co|eq|g[et]|l[et]|sw) |pr$)', name):
        ## Use name as query filter ('<field> <operator> "<value>"')
        data["_queryFilter"] = name
        name = None

    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if len(data):
        url += '&' + urllib_parse.urlencode(data)

    res = requests.get(url, headers=headers)
    data = json.loads(res.text)

    if name is None:
        ## Extract result only from paged data
        data = data["result"]

    return (res, data)


def am_post(token, section, name, data, headers={}, action=None):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if action is not None:
        url += '&_action=' + urllib_parse.quote(action)

    res = requests.post(url, headers=headers, data=json.dumps(data))
    data = json.loads(res.text)

    return (res, data)


def am_put(token, section, name, data, headers={}, action=None):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if action is not None:
        url += '&_action=' + urllib_parse.quote(action)

    res = requests.put(url, headers=headers, data=json.dumps(data))
    data = json.loads(res.text)

    return (res, data)


def am_delete(token, section, name, data={}, headers={}):
    url, headers = am_url_and_headers(token, section, name, headers=headers)
    if len(data):
        url += '&' + urllib_parse.urlencode(data)

    res = requests.delete(url, headers=headers)
    data = json.loads(res.text)

    return (res, data)


## ======================================================================

if __name__ == '__main__':
    logging.basicConfig()
    logformatter = logging.Formatter('%(filename)s: %(levelname)s: %(message)s')
    loghandler = logging.StreamHandler(sys.stderr)
    loghandler.setFormatter(logformatter)
    logger.addHandler(loghandler)

    requests_logger = logging.getLogger("requests.packages.urllib3")
    requests_logger.propagate = True
    requests_logger.addHandler(loghandler)

    if os.environ.get('SSOADMJSON_DEBUG'):
        loghandler.setLevel(logging.DEBUG)
        requests_logger.setLevel(logging.DEBUG)
        http_client.HTTPConnection.debuglevel = 1

    sys.exit(main(sys.argv))
