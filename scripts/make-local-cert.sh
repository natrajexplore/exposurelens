#!/usr/bin/env bash
# Create a local HTTPS certificate for https://nemocve.com (and localhost) in certs/.
#
#   bash scripts/make-local-cert.sh            # Windows: run in Git Bash
#
# Writes certs/nemocve.crt + certs/nemocve.key (server), certs/nemocve-ca.crt + .key (local CA)
# and certs/nemocve.spki (server key pin used by scripts/open-nemocve.bat). The CA is
# name-constrained to nemocve.com and localhost, so even if trusted it can't vouch for any
# other site. certs/ is git-ignored; never commit it.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p certs
cd certs

cat > ca.cnf <<'EOF'
[req]
distinguished_name = dn
prompt = no
x509_extensions = v3_ca
[dn]
CN = ExposureLens Local Dev CA (nemocve.com only)
[v3_ca]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
nameConstraints = critical, permitted;DNS:nemocve.com, permitted;DNS:.nemocve.com, permitted;DNS:localhost, permitted;IP:127.0.0.1/255.255.255.255
EOF

cat > leaf.cnf <<'EOF'
[v3_leaf]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:nemocve.com, DNS:www.nemocve.com, DNS:localhost, IP:127.0.0.1
EOF

export MSYS_NO_PATHCONV=1  # keep Git Bash from rewriting "/CN=..." into a Windows path
openssl req -x509 -newkey rsa:2048 -nodes -keyout nemocve-ca.key -out nemocve-ca.crt -days 365 -config ca.cnf
openssl req -newkey rsa:2048 -nodes -keyout nemocve.key -out nemocve.csr -subj "/CN=nemocve.com"
openssl x509 -req -in nemocve.csr -CA nemocve-ca.crt -CAkey nemocve-ca.key -CAcreateserial \
  -out nemocve.crt -days 365 -extfile leaf.cnf -extensions v3_leaf
openssl x509 -in nemocve.crt -pubkey -noout | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary | openssl base64 > nemocve.spki
rm -f nemocve.csr nemocve-ca.srl

openssl verify -CAfile nemocve-ca.crt nemocve.crt
echo "Server key pin: $(cat nemocve.spki)"
