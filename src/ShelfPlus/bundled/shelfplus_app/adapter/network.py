"""HTTP for the updater (``core/updater.py``) over ``QtNetwork``.

Never ``urllib``: it fails with an SSL error on the home machine (PRD R9.1). Requests
are asynchronous and carry a ``User-Agent``, which GitHub's API requires.

Redirects (GitHub's asset links answer 302 to another host) are followed here, not by
Qt: a redirect policy set as a request attribute from PySide6 reached Qt as a wrapped
Python enum, and Painter 11.1 handed the bare 302 back (v0.9.0) while a newer Qt never
finished the request. The manager is set to ``ManualRedirectPolicy`` with its typed
setter, and every 3xx with a ``Location`` is asked again, never from https to http.
"""

import logging

from PySide6 import QtCore, QtNetwork

from ..core.updater import Response

log = logging.getLogger("ShelfPlus.app.network")

TIMEOUT_MS = 30000  # no data for this long ends the request
MAX_REDIRECTS = 10
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def _header(reply, name):
    """A response header as text; ``rawHeader`` takes bytes or str depending on PySide6."""
    for key in (QtCore.QByteArray(name.encode("ascii")), name):
        try:
            return bytes(reply.rawHeader(key).data()).decode("latin-1").strip()
        except TypeError:
            continue
    return ""


class _Request:
    """The handle ``get`` returns; it follows the request across redirects."""

    def __init__(self, http, url, on_done, accept):
        self._http = http
        self.url = url
        self.on_done = on_done
        self.accept = accept
        self.redirects = 0
        self.reply = None

    def abort(self):
        reply, self.reply = self.reply, None
        self.on_done = None
        if reply is not None:
            self._http._forget(reply)
            reply.abort()
            reply.deleteLater()


class QtHttp:
    """``get(url, on_done, accept=None)`` as the updater expects it."""

    def __init__(self, user_agent):
        self.user_agent = user_agent
        self._manager = QtNetwork.QNetworkAccessManager()
        self._manager.setRedirectPolicy(QtNetwork.QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        self._pending = {}  # reply -> _Request; the reference keeps the reply alive

    def get(self, url, on_done, accept=None):
        handle = _Request(self, url, on_done, accept)
        self._send(handle)
        return handle

    def _send(self, handle):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(handle.url))
        request.setRawHeader(b"User-Agent", self.user_agent.encode("utf-8"))
        if handle.accept:
            request.setRawHeader(b"Accept", handle.accept.encode("utf-8"))
        request.setTransferTimeout(TIMEOUT_MS)
        reply = self._manager.get(request)
        handle.reply = reply
        self._pending[reply] = handle
        reply.finished.connect(lambda: self._finished(reply))

    def _forget(self, reply):
        return self._pending.pop(reply, None)

    def _finished(self, reply):
        handle = self._forget(reply)
        if handle is None or handle.on_done is None:  # aborted
            return
        try:
            status = reply.attribute(QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            status = int(status) if status is not None else None
            if status in REDIRECT_STATUSES:
                target = self._redirect_target(reply)
                log.info("GET %s -> %s, to %s", handle.url, status, target or "nowhere")
                if target is None:
                    return self._done(handle, Response(status=status, error="GitHub's redirect could not be followed"))
                if handle.redirects >= MAX_REDIRECTS:
                    return self._done(handle, Response(status=status, error="too many redirects"))
                handle.redirects += 1
                handle.url = target
                return self._send(handle)
            error = None
            if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
                error = reply.errorString() or "the network request failed"
            body = bytes(reply.readAll().data())
        except Exception:
            log.exception("Reading the network reply failed")
            status, body, error = None, b"", "the network reply could not be read"
        finally:
            reply.deleteLater()
        log.info("GET %s -> %s%s", handle.url, status, f" ({error})" if error else "")
        self._done(handle, Response(status=status, body=body, error=error))

    def _redirect_target(self, reply):
        """The absolute URL a 3xx points to, or ``None`` (none given, or https -> http)."""
        location = reply.attribute(QtNetwork.QNetworkRequest.Attribute.RedirectionTargetAttribute)
        if not isinstance(location, QtCore.QUrl) or location.isEmpty():
            location = QtCore.QUrl(_header(reply, "Location"))
        if location.isEmpty():
            return None
        current = reply.url()
        target = current.resolved(location)
        if not target.isValid() or target.scheme() not in ("http", "https"):
            return None
        if current.scheme() == "https" and target.scheme() != "https":
            return None
        return target.toString(QtCore.QUrl.ComponentFormattingOption.FullyEncoded)

    def _done(self, handle, response):
        on_done, handle.on_done, handle.reply = handle.on_done, None, None
        if on_done is not None:
            on_done(response)

    def close(self):
        for reply, handle in list(self._pending.items()):
            self._forget(reply)
            handle.on_done = None
            try:
                reply.abort()
                reply.deleteLater()
            except Exception:
                pass
        self._manager.deleteLater()
