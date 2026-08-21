#!/usr/bin/env bash
# Ollama on an Oracle Cloud Always Free ARM box, reachable by the API and
# nobody else.
#
# Run as cloud-init user data, or paste into a fresh Ubuntu 22.04 aarch64
# instance (VM.Standard.A1.Flex, 4 OCPU / 24 GB — the always-free shape).
#
# Why the proxy. Ollama binds an unauthenticated API, and an open one on a
# public address is found by scanners in days: free inference for whoever wants
# it, on a box registered to you. So Caddy sits in front, terminates HTTPS, and
# demands a bearer token. The token is the same value the API sends as
# PASHU_FALLBACK_API_KEY.
#
# Why nip.io. Let's Encrypt will not issue a certificate for a bare IP, and this
# box has no domain. `1-2-3-4.nip.io` resolves to 1.2.3.4 without registering
# anything, so Caddy can get a real certificate and the API does not have to
# skip verification — which would undo the point of the token.
#
#   sudo OLLAMA_TOKEN='<a long random string>' bash oracle-ollama.sh
#
# Afterwards, open port 443 in BOTH places or nothing reaches it: the instance's
# security list in the OCI console, and the local firewall (this script does the
# second). Oracle's Ubuntu images ship with iptables rules that drop everything.

set -euo pipefail

MODEL="${MODEL:-qwen2.5:7b}"
TOKEN="${OLLAMA_TOKEN:?set OLLAMA_TOKEN to a long random string}"

IP="$(curl -fsS https://api.ipify.org)"
HOST="${IP//./-}.nip.io"

echo "==> host will be ${HOST}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl debian-keyring debian-archive-keyring apt-transport-https

# --- Ollama, bound to localhost only -----------------------------------------
# The default binds 0.0.0.0. Left that way the proxy is decoration, because
# port 11434 answers directly and skips the token entirely.
curl -fsSL https://ollama.com/install.sh | sh
mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/override.conf <<'UNIT'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
# Keep the model resident. Loading 4 GB from disk on every request is most of
# the latency on a CPU box, and this one has memory to spare.
Environment="OLLAMA_KEEP_ALIVE=-1"
UNIT
systemctl daemon-reload
systemctl enable --now ollama
sleep 5
ollama pull "${MODEL}"

# --- Caddy: HTTPS and the token ----------------------------------------------
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  > /etc/apt/sources.list.d/caddy-stable.list
apt-get update -qq
apt-get install -y -qq caddy

cat >/etc/caddy/Caddyfile <<CADDY
${HOST} {
	@authorized header Authorization "Bearer ${TOKEN}"

	handle @authorized {
		reverse_proxy 127.0.0.1:11434 {
			# A 7B model on four ARM cores answers in tens of seconds. The
			# default read timeout cuts that off mid-generation and reports a
			# gateway error, which looks like the box is broken when it is
			# merely slow.
			transport http {
				read_timeout 300s
			}
		}
	}

	handle {
		respond "unauthorized" 401
	}
}
CADDY

systemctl reload caddy || systemctl restart caddy

# --- firewall ----------------------------------------------------------------
# Oracle's Ubuntu images drop inbound traffic by default, and the rule has to be
# inserted before the REJECT at the end of the chain rather than appended after
# it.
iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT || iptables -I INPUT -p tcp --dport 443 -j ACCEPT
iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT || iptables -I INPUT -p tcp --dport 80 -j ACCEPT
netfilter-persistent save 2>/dev/null || true

cat <<DONE

==> done

  endpoint : https://${HOST}/v1
  model    : ${MODEL}

Set these where the API is deployed, then redeploy:

  PASHU_MODEL_PROVIDER=failover
  PASHU_FALLBACK_BASE_URL=https://${HOST}/v1
  PASHU_FALLBACK_MODEL=${MODEL}
  PASHU_FALLBACK_API_KEY=<the token>
  PASHU_FALLBACK_REQUIRES_KEY=true

Still to do in the OCI console: allow 443 in the subnet's security list.
Check it from elsewhere:

  curl -s https://${HOST}/v1/models -H "Authorization: Bearer <token>"
  curl -s https://${HOST}/v1/models          # must answer 401
DONE
