#!/usr/bin/env python3
"""KrakenQ — petite IA spécialisée Quant dev, avec conversations en onglets.

    python app.py                 # lance le serveur local puis ouvre l'interface
    python app.py --ask "C'est quoi une API ?"     # pose une question directement dans le terminal

Projet fun : prototype éducatif, pas un conseil d'investissement, pas pour de l'argent réel.
Bibliothèque standard uniquement : rien à installer (pensé pour Termux).
Trois « cerveaux », choisis dans ⚙️ Réglages ou via .env :
    • Claude (Anthropic)            — clé ANTHROPIC_API_KEY
    • Compatible OpenAI             — OpenAI, Groq, OpenRouter, Mistral, Ollama, llama.cpp… (OPENAI_*)
    • Hors-ligne                    — base de connaissances intégrée (brain.py), aucune clé requise
"""
import argparse
import ipaddress
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))  # robuste même lancé depuis un autre dossier
import brain  # noqa: E402

APP_NAME = "KrakenQ"
VERSION = "1.0"
ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CONFIG_PATH = ROOT / "config.json"
ENV_PATH = ROOT / ".env"

MAX_BODY = 512 * 1024
TRUNC_NOTE = "\n\n> ⚠️ Réponse tronquée (limite de longueur atteinte). Écris « continue » pour la suite."

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/vnd.microsoft.icon", ".ico")

# --------------------------------------------------------------------------------------
# Réglages : valeurs par défaut < config.json (écrit par l'interface) < .env < variables d'environnement
# --------------------------------------------------------------------------------------

DEFAULTS = {
    "provider": "auto",  # auto | anthropic | openai | offline
    "anthropic_api_key": "",
    "anthropic_model": "claude-haiku-5-5",
    "anthropic_base_url": "https://api.anthropic.com",
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "max_tokens": 1500,
}
ENV_MAP = {
    "KRAKENQ_PROVIDER": "provider",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "ANTHROPIC_MODEL": "anthropic_model",
    "ANTHROPIC_BASE_URL": "anthropic_base_url",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "OPENAI_MODEL": "openai_model",
    "KRAKENQ_MAX_TOKENS": "max_tokens",
}
PROVIDERS = ("auto", "anthropic", "openai", "offline")
SECRET_FIELDS = ("anthropic_api_key", "openai_api_key")


def read_dotenv():
    env = {}
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            env[k.strip().removeprefix("export ").strip()] = v
    except OSError:
        pass
    return env


class Settings:
    def __init__(self):
        self.lock = threading.Lock()
        self.saved = {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.saved = {k: v for k, v in data.items() if k in DEFAULTS}
        except (OSError, ValueError):
            pass

    def effective(self):
        with self.lock:
            cfg = dict(DEFAULTS)
            cfg.update(self.saved)
        env = {**read_dotenv(), **os.environ}
        for env_key, key in ENV_MAP.items():
            if env.get(env_key):
                cfg[key] = env[env_key].strip()
        try:
            cfg["max_tokens"] = max(64, min(8000, int(cfg["max_tokens"])))
        except (TypeError, ValueError):
            cfg["max_tokens"] = DEFAULTS["max_tokens"]
        if cfg["provider"] not in PROVIDERS:
            cfg["provider"] = "auto"
        return cfg

    def update(self, patch):
        """Applique un patch venant de l'interface. Clé absente/vide = inchangée ; null = effacer (clés)."""
        if not isinstance(patch, dict):
            raise ValueError("format invalide")
        new = {}
        if "provider" in patch:
            if patch["provider"] not in PROVIDERS:
                raise ValueError("fournisseur inconnu")
            new["provider"] = patch["provider"]
        for key in SECRET_FIELDS:
            if key in patch:
                if patch[key] is None:
                    new[key] = ""
                elif isinstance(patch[key], str) and patch[key].strip():
                    new[key] = patch[key].strip()[:400]
        for key in ("anthropic_model", "openai_model"):
            if isinstance(patch.get(key), str) and patch[key].strip():
                new[key] = patch[key].strip()[:120]
        if isinstance(patch.get("openai_base_url"), str) and patch["openai_base_url"].strip():
            url = patch["openai_base_url"].strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                raise ValueError("l'adresse doit commencer par http:// ou https://")
            new["openai_base_url"] = url[:300]
        if "max_tokens" in patch:
            try:
                new["max_tokens"] = max(64, min(8000, int(patch["max_tokens"])))
            except (TypeError, ValueError):
                raise ValueError("max_tokens doit être un nombre")
        with self.lock:
            self.saved.update(new)
            tmp = CONFIG_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.saved, indent=2, ensure_ascii=False), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, CONFIG_PATH)


SETTINGS = Settings()


def mask(key):
    return ("••••" + key[-4:]) if key else ""


def is_private_url(url):
    host = urlsplit(url).hostname or ""
    if host in ("localhost", "::1") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def resolve_provider(cfg):
    """Renvoie (fournisseur_effectif, remarque). La remarque explique un repli éventuel."""
    wanted = cfg["provider"]
    if wanted == "offline":
        return "offline", ""
    if wanted in ("auto", "anthropic") and cfg["anthropic_api_key"]:
        return "anthropic", ""
    if wanted in ("auto", "openai") and (cfg["openai_api_key"] or (wanted == "openai" and is_private_url(cfg["openai_base_url"]))):
        return "openai", ""
    if wanted == "auto":
        return "offline", ""
    return "offline", "clé API manquante pour le fournisseur choisi"


def model_of(cfg, provider):
    return {"anthropic": cfg["anthropic_model"], "openai": cfg["openai_model"]}.get(provider, "base intégrée")


def public_view(cfg):
    provider, note = resolve_provider(cfg)
    return {
        "app": APP_NAME,
        "version": VERSION,
        "provider": cfg["provider"],
        "resolved": provider,
        "note": note,
        "model": model_of(cfg, provider),
        "anthropic_model": cfg["anthropic_model"],
        "openai_base_url": cfg["openai_base_url"],
        "openai_model": cfg["openai_model"],
        "max_tokens": cfg["max_tokens"],
        "anthropic_key": mask(cfg["anthropic_api_key"]),
        "openai_key": mask(cfg["openai_api_key"]),
    }


# --------------------------------------------------------------------------------------
# Fournisseurs (flux de texte)
# --------------------------------------------------------------------------------------


class ProviderError(Exception):
    def __init__(self, message, code=None, body=""):
        super().__init__(message)
        self.code, self.body = code, body


def http_error_message(code, body):
    detail = ""
    try:
        data = json.loads(body)
        err = data.get("error", data) if isinstance(data, dict) else data
        detail = err.get("message", "") if isinstance(err, dict) else str(err)
    except ValueError:
        detail = body.strip()[:200]
    hints = {
        400: "Requête refusée (400)",
        401: "Clé API refusée (401) — vérifie-la dans ⚙️ Réglages",
        403: "Accès refusé (403) — droits ou région non autorisés",
        404: "Modèle ou adresse introuvable (404) — vérifie le nom du modèle",
        413: "Conversation trop longue (413)",
        429: "Limite de débit ou crédit épuisé (429)",
    }
    hint = hints.get(code) or ("Service momentanément indisponible (%d)" % code if code >= 500 else "Erreur HTTP %d" % code)
    return hint + (" : " + detail[:300] if detail else "")


def open_stream(url, headers, payload, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read(4000).decode("utf-8", "replace")
        raise ProviderError(http_error_message(e.code, body), e.code, body)
    except urllib.error.URLError as e:
        raise ProviderError("Impossible de joindre le service (%s)" % getattr(e, "reason", e))
    except (TimeoutError, socket.timeout):
        raise ProviderError("Délai dépassé : le service ne répond pas")
    except OSError as e:
        raise ProviderError("Erreur réseau (%s)" % e)


def sse_events(resp):
    """Itère sur les lignes « data: … » d'un flux SSE et renvoie la charge brute (str)."""
    try:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    yield data
    except (TimeoutError, socket.timeout):
        raise ProviderError("Connexion interrompue (délai dépassé)")
    except OSError as e:
        raise ProviderError("Connexion interrompue (%s)" % e)


def stream_anthropic(cfg, messages):
    payload = {
        "model": cfg["anthropic_model"],
        "max_tokens": cfg["max_tokens"],
        "system": brain.SYSTEM_PROMPT,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "content-type": "application/json",
        "accept": "text/event-stream",
        "x-api-key": cfg["anthropic_api_key"],
        "anthropic-version": "2023-06-01",
        "user-agent": "%s/%s" % (APP_NAME, VERSION),
    }
    url = cfg["anthropic_base_url"].rstrip("/") + "/v1/messages"
    with open_stream(url, headers, payload) as resp:
        for data in sse_events(resp):
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            kind = ev.get("type")
            if kind == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta" and d.get("text"):
                    yield d["text"]
            elif kind == "message_delta":
                if (ev.get("delta") or {}).get("stop_reason") == "max_tokens":
                    yield TRUNC_NOTE
            elif kind == "error":
                err = ev.get("error") or {}
                raise ProviderError("Erreur du service : %s" % err.get("message", "inconnue"))
            elif kind == "message_stop":
                break


def stream_openai(cfg, messages):
    payload = {
        "model": cfg["openai_model"],
        "stream": True,
        "max_tokens": cfg["max_tokens"],
        "messages": [{"role": "system", "content": brain.SYSTEM_PROMPT}] + messages,
    }
    headers = {
        "content-type": "application/json",
        "accept": "text/event-stream",
        "user-agent": "%s/%s" % (APP_NAME, VERSION),
    }
    if cfg["openai_api_key"]:
        headers["authorization"] = "Bearer " + cfg["openai_api_key"]
    url = cfg["openai_base_url"].rstrip("/") + "/chat/completions"
    try:
        resp = open_stream(url, headers, payload)
    except ProviderError as e:
        # Les modèles récents d'OpenAI exigent max_completion_tokens au lieu de max_tokens.
        if e.code == 400 and "max_completion_tokens" in e.body:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
            resp = open_stream(url, headers, payload)
        else:
            raise
    with resp:
        for data in sse_events(resp):
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if isinstance(ev.get("error"), dict):
                raise ProviderError("Erreur du service : %s" % ev["error"].get("message", "inconnue"))
            for choice in ev.get("choices") or []:
                text = (choice.get("delta") or {}).get("content")
                if text:
                    yield text
                if choice.get("finish_reason") == "length":
                    yield TRUNC_NOTE


def stream_offline(messages):
    words = brain.answer(messages).split(" ")
    for i in range(0, len(words), 4):
        yield " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")
        time.sleep(0.01)


def run_chat(cfg, messages, emit):
    """Pilote une réponse : emit(dict) envoie chaque évènement au navigateur (ou au terminal)."""
    provider, note = resolve_provider(cfg)
    emit({"t": "meta", "provider": provider, "model": model_of(cfg, provider), "note": note})
    if provider != "offline":
        gen = stream_anthropic(cfg, messages) if provider == "anthropic" else stream_openai(cfg, messages)
        produced = False
        try:
            for chunk in gen:
                produced = True
                emit({"t": "delta", "v": chunk})
            if produced:
                emit({"t": "done"})
                return
            raise ProviderError("Réponse vide du service")
        except ProviderError as e:
            if produced:
                emit({"t": "delta", "v": "\n\n> ⚠️ Réponse interrompue : %s" % e})
                emit({"t": "done"})
                return
            # Repli automatique : l'utilisateur obtient quand même une réponse (réseau mobile capricieux, quota…)
            emit({"t": "fallback", "v": str(e)})
            emit({"t": "meta", "provider": "offline", "model": model_of(cfg, "offline"), "note": str(e)})
        finally:
            gen.close()
    for chunk in stream_offline(messages):
        emit({"t": "delta", "v": chunk})
    emit({"t": "done"})


def clean_messages(raw):
    if not isinstance(raw, list):
        raise ValueError("« messages » doit être une liste")
    out = []
    for m in raw[-40:]:
        if not isinstance(m, dict):
            continue
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:20000]
        if not content:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    if not out or out[-1]["role"] != "user":
        raise ValueError("le dernier message doit venir de l'utilisateur")
    return out


# --------------------------------------------------------------------------------------
# Serveur HTTP
# --------------------------------------------------------------------------------------

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


class Handler(BaseHTTPRequestHandler):
    server_version = APP_NAME + "/" + VERSION

    def log_message(self, fmt, *args):  # silence : on n'affiche que l'essentiel
        pass

    # -- utilitaires -------------------------------------------------------------------
    def _common_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self._common_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _guard(self):
        """Refuse les requêtes qui ne viennent pas de notre propre page (anti-CSRF / DNS rebinding)."""
        host = self.headers.get("Host", "")
        hostname = host.rsplit(":", 1)[0].strip("[]") if not host.startswith("[") else host.split("]")[0].strip("[")
        if self.server.strict_host and hostname not in LOOPBACK_HOSTS and not hostname.endswith(".localhost"):
            self._json({"error": "hôte non autorisé"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin != "null" and urlsplit(origin).netloc != host:
            self._json({"error": "origine non autorisée"}, 403)
            return False
        return True

    def _body_json(self):
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ValueError("Content-Type application/json requis")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Content-Length invalide")
        if length <= 0 or length > MAX_BODY:
            raise ValueError("corps de requête vide ou trop gros")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ValueError("JSON invalide")

    # -- routes ------------------------------------------------------------------------
    def do_GET(self):
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            return self._json(public_view(SETTINGS.effective()))
        if path.startswith("/api/"):
            return self._json({"error": "introuvable"}, 404)
        self._static(path)

    do_HEAD = do_GET

    def do_POST(self):
        if not self._guard():
            return
        path = urlsplit(self.path).path
        try:
            data = self._body_json()
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        if path == "/api/chat":
            return self._chat(data)
        if path == "/api/settings":
            try:
                SETTINGS.update(data)
            except (ValueError, OSError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json(public_view(SETTINGS.effective()))
        self._json({"error": "introuvable"}, 404)

    def _chat(self, data):
        try:
            messages = clean_messages(data.get("messages") if isinstance(data, dict) else None)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self._common_headers()
        self.end_headers()

        def emit(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        try:
            run_chat(SETTINGS.effective(), messages, emit)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # l'onglet a été fermé ou la réponse stoppée : on abandonne proprement
        except Exception as e:  # filet de sécurité : ne jamais laisser le navigateur sans fin de flux
            try:
                emit({"t": "error", "v": "Erreur interne : %s" % e})
            except OSError:
                pass

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (WEB / rel).resolve()
        web_root = WEB.resolve()
        if target != web_root and web_root not in target.parents:
            return self._json({"error": "introuvable"}, 404)
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            return self._json({"error": "introuvable"}, 404)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/manifest+json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        cache = "max-age=86400" if target.suffix in (".png", ".ico", ".svg") else "no-cache"
        self._send(200, target.read_bytes(), ctype, {"Cache-Control": cache})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    strict_host = True


# --------------------------------------------------------------------------------------
# Lancement
# --------------------------------------------------------------------------------------

BANNER = r"""
   ,-.,-.      {name} {version}  ·  IA spécialisée Quant dev
  (  oo  )     cerveau : {brain}
  /|/||\|\     interface : {url}
  ~ ~ ~~ ~ ~   Ctrl+C pour arrêter
"""


def open_in_browser(url):
    time.sleep(0.6)
    try:
        if shutil.which("termux-open-url"):
            subprocess.run(["termux-open-url", url], timeout=10, check=False)
        else:
            webbrowser.open(url)
    except Exception:
        pass


def ask_cli(question):
    cfg = SETTINGS.effective()

    def emit(ev):
        if ev["t"] == "delta":
            print(ev["v"], end="", flush=True)
        elif ev["t"] == "fallback":
            print("[repli hors-ligne : %s]\n" % ev["v"])

    run_chat(cfg, clean_messages([{"role": "user", "content": question}]), emit)
    print()


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="KrakenQ — petite IA spécialisée Quant dev")
    ap.add_argument("--host", default="127.0.0.1", help="adresse d'écoute (défaut : 127.0.0.1, ce téléphone/PC seulement)")
    ap.add_argument("--port", type=int, default=8787, help="port (défaut : 8787 ; le suivant est essayé s'il est occupé)")
    ap.add_argument("--no-open", action="store_true", help="ne pas ouvrir le navigateur automatiquement")
    ap.add_argument("--ask", metavar="QUESTION", help="poser une question dans le terminal puis quitter")
    args = ap.parse_args()

    if args.ask:
        try:
            return ask_cli(args.ask)
        except BrokenPipeError:  # ex. « | head » : sortie fermée par le lecteur
            return

    server = None
    for port in range(args.port, args.port + 10):
        try:
            server = Server((args.host, port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit("Aucun port libre entre %d et %d." % (args.port, args.port + 9))
    server.strict_host = args.host in LOOPBACK_HOSTS
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = "http://%s:%d" % (shown, server.server_address[1])

    cfg = SETTINGS.effective()
    provider, note = resolve_provider(cfg)
    label = {"anthropic": "Claude (%s)" % cfg["anthropic_model"], "openai": "compatible OpenAI (%s)" % cfg["openai_model"], "offline": "hors-ligne (base intégrée)"}[provider]
    print(BANNER.format(name=APP_NAME, version=VERSION, brain=label, url=url))
    print("  Projet fun : prototype éducatif, pas pour investir de l'argent réel.\n")
    if provider == "offline":
        print("  Astuce : ajoute une clé API dans ⚙️ Réglages (ou .env) pour des réponses libres.\n")
    if args.host not in LOOPBACK_HOSTS:
        print("  ⚠️  Écoute sur %s : toute personne de ton réseau peut utiliser tes crédits API. Réseau de confiance uniquement.\n" % args.host)

    if not args.no_open:
        threading.Thread(target=open_in_browser, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nÀ bientôt 🐙")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
