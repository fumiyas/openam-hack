OpenAM hacks (junk tools and misc)
======================================================================

* Copyright (c) 2017 SATOH Fumiyasu @ OSS Technology Corp., Japan
* License: GNU General Public License version 3

What's this?
---------------------------------------------------------------------

Blah, Blah.
I'm here! I'm here!

`ssoadmjson`
---------------------------------------------------------------------

WARNING: Currently, server certificate verification is not performed!

### How to install, setup

```console
$ sed 's|/opt/osstech/|/usr/local/|' bin/ssoadmjson.py >bin/ssoadmjson
$ sudo install -d -m 0755 /usr/local/bin/ssoadmjson
$ sudo install -m 0755 bin/ssoadmjson /usr/local/bin/ssoadmjson
$ sudo install -d -m 0755 /usr/local/etc/openam
$ sudo install -m 0640 etc/ssoadmjson.conf /usr/local/etc/openam/
$ sudoedit /usr/local/etc/openam/ssoadmjson.conf
...
```

### Usage

Show help message:

```console
# ssoadmjson --help
...help messages...
```

Realms operation:

```console
# echo '{"realm": "SiteRealm"}' |ssoadmjson create realms
{
    "realmCreated": "/SiteRealm"
}
# ssoadmjson read realms
[
    "/",
        "/SiteRealm"
	]
# ssoadmjson delete realms /SiteRealm
{
    "success": "true"
}
```

Resource Type operation:

```console
# cat resourcetype-url.json
{
  "name": "URLResourceType",
  "actions": {
    "HEAD": true,
    "GET": true,
    "POST": true
  },
  "patterns": [
    "*://*:*/*",
    "*://*:*/*?*"
  ]
}
# ssoadmjson create resourcetypes <resourcetype-url.json
{
    "actions": {
        "GET": true,
        "HEAD": true,
        "POST": true
    },
    "description": null,
    "name": "URLResourceType",
    "patterns": [
        "*://*:*/*",
        "*://*:*/*?*"
    ],
    "uuid": "b99c6ad0-8274-4b60-95bc-98b9b51b54e7"
}
# /opt/osstech/bin/ssoadmjson get resourcetypes b99c6ad0-8274-4b60-95bc-98b9b51b54e7
{
    "actions": {
        "GET": true,
        "HEAD": true,
        "POST": true
    },
    "description": "",
    "name": "URLResourceType",
    "patterns": [
        "*://*:*/*",
        "*://*:*/*?*"
    ],
    "uuid": "b99c6ad0-8274-4b60-95bc-98b9b51b54e7"
}
# /opt/osstech/bin/ssoadmjson get resourcetypes 'name co "URL"'
[
    {
        "actions": {
            "GET": true,
            "HEAD": true,
            "POST": true
        },
        "description": "",
        "name": "URLResourceType",
        "patterns": [
            "*://*:*/*",
            "*://*:*/*?*"
        ],
        "uuid": "b99c6ad0-8274-4b60-95bc-98b9b51b54e7"
    },
    {
        "actions": {
            "DELETE": true,
            "GET": true,
            "HEAD": true,
            "OPTIONS": true,
            "PATCH": true,
            "POST": true,
            "PUT": true
        },
        "description": "The built-in URL Resource Type available to OpenAM Policies.",
        "name": "URL",
        "patterns": [
            "*://*:*/*",
            "*://*:*/*?*"
        ],
        "uuid": "76656a38-5f8e-401b-83aa-4ccb74ce88d2"
    }
]
```

### References

* 2. Developing Client Applications - OpenAM Developer's Guide - Docs - ForgeRock BackStage
  * https://backstage.forgerock.com/docs/openam/13.5/dev-guide/chap-client-dev#rest-api-authz-resource-types-update
