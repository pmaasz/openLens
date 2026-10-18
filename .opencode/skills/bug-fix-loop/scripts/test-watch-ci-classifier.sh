#!/usr/bin/env bash
# Check that is_transport_error separates "could not ask" from "CI said no".
#
# Extracted from watch-ci.sh so the classifier itself can be verified against
# known inputs. A widened pattern that swallowed a genuine failure would be
# the same bug pointed the other way, so this covers both directions.
set -uo pipefail

# shellcheck source=/dev/null
source <(sed -n '/^is_transport_error()/,/^}/p' \
  "$(dirname "$0")/watch-ci.sh")

pass=0
fail=0

expect() {
  local want="$1" label="$2" text="$3"
  if is_transport_error "$text"; then got=transport; else got=result; fi
  if [[ "$got" == "$want" ]]; then
    printf '  ok    %-13s %s\n' "$label" "${text:0:56}"
    pass=$((pass + 1))
  else
    printf '  FAIL  %-13s %s\n' "${got} (wanted ${want})" "${text:0:56}"
    fail=$((fail + 1))
  fi
}

echo "must be treated as transport failures:"
expect transport tls-timeout \
  'Post "https://api.github.com/graphql": net/http: TLS handshake timeout'
expect transport run-list 'failed to get runs: net/http: TLS handshake timeout'
expect transport dns 'Could not resolve to host: github.com'
expect transport dns-short 'dial tcp: lookup github.com: no such host'
expect transport io-timeout 'i/o timeout'
expect transport refused 'dial tcp 140.82.121.4:443: connect: connection refused'
expect transport bad-gateway '502 Bad Gateway'
expect transport unavailable '503 Service Unavailable'

echo "must NOT be treated as transport failures:"
expect result job-failed 'Test (py3.12)	fail	2m12s'
expect result job-passed 'Build	pass	14s'
expect result job-pending 'Test (py3.10)	pending	0'
expect result pr-missing \
  'GraphQL: Could not resolve to a PullRequest with the number 518.'
expect result cancelled 'Error: could not merge pull request'

echo
echo "passed ${pass}, failed ${fail}"
[[ $fail -eq 0 ]]