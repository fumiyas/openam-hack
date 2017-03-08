#!/bin/bash
##
## OpenAM: Reset amAdmin's password by OpenDJ admin (cn=Directory Manager)
## Copyright (c) 2017 SATOH Fumiyasu @ OSS Technology Corp., Japan
##
## License: GNU General Public License version 3
##
## Requirements:
##   OpenLDAP ldapsearch(1), ldapmodify(1)
##   OpenSSL openssl(1)
##   OpenAM ampassword
##

set -u
set -o pipefail

export LC_ALL="C"
export PATH="/bin:/usr/bin:/opt/osstech/bin"

ldap_uri="ldap://localhost:50389/"

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 BIND_DN BIND_PW_FILE AMADMIN_PW_FILE"
  exit 1
fi

bind_dn="$1"; shift
bind_pw_file="$1"; shift
admin_pw_file="$1"; shift

ldap_suffix=$(
  ldapsearch \
    -LLL \
    -o ldif-wrap=no \
    -H "$ldap_uri" \
    -x \
    -b '' \
    -s base \
    namingContexts \
  |sed -n '1d;s/^[^:]*: //p' \
  ;
) || exit $?

amadmin_dn="ou=amAdmin,ou=users,ou=default,ou=GlobalConfig,ou=1.0,ou=sunIdentityRepositoryService,ou=services,$ldap_suffix"

amadmin_pw_encrypted=$(
  head -n 1 "$admin_pw_file" \
  |tr -d '\n' \
  |openssl dgst -sha1 -binary \
  |openssl base64 \
  |ampassword --encrypt /dev/stdin \
  ;
) || exit $?

amadmin_sunkeyvalues=$(
  ldapsearch \
    -H "$ldap_uri" \
    -x \
    -D "$bind_dn" \
    -y <(head -n 1 "$bind_pw_file" |tr -d '\n') \
    -LLL \
    -o ldif-wrap=no \
    -b "$amadmin_dn" \
    '(objectClass=*)' \
    sunKeyValue \
  |sed '1d' \
  |grep -iv '^sunKeyValue: userPassword=' \
  ;
) || exit $?

cat <<EOF \
|ldapmodify \
  -H "$ldap_uri" \
  -x \
  -D "$bind_dn" \
  -y <(head -n 1 "$bind_pw_file" |tr -d '\n') \
;
dn: $amadmin_dn
changetype: modify
replace: sunKeyValue
$amadmin_sunkeyvalues
sunKeyValue: userPassword=$amadmin_pw_encrypted
EOF
