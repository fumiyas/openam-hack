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

pdie() { echo "$0: ERROR: ${1-}" 1>&2; exit "${2-1}"; }

ldap_uri="ldap://localhost:50389/"
admin_name="amAdmin"
disable_password=""
usage="Usage: $0 [OPTIONS] BIND_DN BIND_PW_FILE [AMADMIN_PW_FILE]"
help="$usage

Options [default]:
  -H, --ldap-uri URI
    LDAP server (OpenDJ) URI [$ldap_uri]
  -n, --name NAME
    Username to reset its password [$admin_name]
  -D, --disable-password
    Disable password

Arguments:
  BIND_DN
    Distinguished name to bind to the LDAP server
  BIND_PW_FILE
    Filename to read the bind password
  AMADMIN_PW_FILE
    Filename to read the new password for the target user
    (Read stdin if no --disable-password and this argument)

Examples:
  Reset amAdmin's password:
    $ ${0##*/} 'cn=Directory Manager' DirectoryManager.password amAdmin.password
  Disable UrlAccessAgent's password:
    $ ${0##*/} -n amService-URLAccessAgent -D 'cn=Directory Manager' DirectoryManager.password
"

while [[ $# -gt 0 ]]; do
  opt="$1"; shift

  case "$opt" in
  -h|--help)
    echo "$help"
    exit 1
    ;;
  -H|--ldap-uri)
    [[ $# -lt 1 ]] && pdie "Option requires an argument: $opt"
    ldap_uri="$1"; shift
    ;;
  -n|--name)
    [[ $# -lt 1 ]] && pdie "Option requires an argument: $opt"
    admin_name="$1"; shift
    ;;
  -D|--disable-password)
    disable_password="set"
    ;;
  --)
    break
    ;;
  -*)
    pdie "Invalid option: $opt"
    ;;
  *)
    set -- "$opt" ${1+"$@"}
    break
    ;;
  esac
done

if [[ $# -lt 2 ]]; then
  echo "$usage"
  exit 1
fi

bind_dn="$1"; shift
bind_pw_file="$1"; shift
admin_pw_file="${1-}"; ${1+shift}

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

amadmin_dn="ou=$admin_name,ou=users,ou=default,ou=GlobalConfig,ou=1.0,ou=sunIdentityRepositoryService,ou=services,$ldap_suffix"

if [[ -n $disable_password ]]; then
  amadmin_pw_encrypted="XXXXXXXX_PASSWORD_IS_DISABLED_XXXXXXXX"
else
  amadmin_pw_encrypted=$(
    head -n 1 "${admin_pw_file:-/dev/stdin}" \
    |tr -d '\n' \
    |openssl dgst -sha1 -binary \
    |openssl base64 \
    |ampassword --encrypt /dev/stdin \
    ;
  ) || exit $?
fi

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
sunKeyValue: userPassword=$amadmin_pw_encrypted
$amadmin_sunkeyvalues
EOF
