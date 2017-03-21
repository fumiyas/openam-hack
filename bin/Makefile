TARGETS=		ampasswordreset ssoadmjson

prefix=			/opt/osstech
sysconfdir=		$(prefix)/etc
bindir=			$(prefix)/bin
localstatedir=		$(prefix)/var

OPENAM_BASE_DIR=	$(localstatedir)/lib/tomcat/openam
OPENAM_SYSCONF_DIR=	$(sysconfdir)/openam
OPENAM_BIN_DIR=		$(bindir)

SED=sed
SED_EXPR= \
  -e 's|@OPENAM_BASE_DIR@|$(OPENAM_BASE_DIR)|g' \
  -e 's|@OPENAM_SYSCONF_DIR@|$(OPENAM_SYSCONF_DIR)|g' \
  -e 's|@OPENAM_BIN_DIR@|$(OPENAM_BIN_DIR)|g'

SUBST= \
  $(SED) $(SED_EXPR) $< >$@.$$$$.tmp \
  && chmod +x $@.$$$$.tmp \
  && mv $@.$$$$.tmp $@ \
  || $(RM) $@.$$$$.tmp

## ======================================================================

default: build

build: $(TARGETS)

clean:
	$(RM) $(TARGETS) *.tmp

ampasswordreset: ampasswordreset.bash
	$(SUBST)

ssoadmjson: ssoadmjson.py
	$(SUBST)
