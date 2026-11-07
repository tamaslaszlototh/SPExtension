"""HTTP for the updater (``core/updater.py``) over ``QtNetwork``.

Never ``urllib``: it fails with an SSL error on the home machine (PRD R9.1). Requests
are asynchronous, follow redirects (GitHub's asset links answer 302 to another host)
and carry a ``User-Agent``, which GitHub's API requires.
"""

import logging

from PySide6 import QtCore, QtNetwork

from ..core.updater import Response

log = logging.getLogger("ShelfPlus.app.network")

TIMEOUT_MS = 30000  # no data for this long ends the request


class _Request:
    def __init__(self, http, reply):
        self._http = http
        self._reply = reply

    def abort(self):
        reply, self._reply = self._reply, None
        if reply is not None:
            self._http._forget(reply)
            reply.abort()
            reply.deleteLater()


class QtHttp:
    """``get(url, on_done, accept=None)`` as the updater expects it."""

    def __init__(self, user_agent):
        self.user_agent = user_agent
        self._manager = QtNetwork.QNetworkAccessManager()
        self._pending = {}  # reply -> on_done; the reference keeps the reply alive

    def get(self, url, on_done, accept=None):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b"User-Agent", self.user_agent.encode("utf-8"))
        if accept:
            request.setRawHeader(b"Accept", accept.encode("utf-8"))
        request.setAttribute(
            QtNetwork.QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QtNetwork.QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        request.setTransferTimeout(TIMEOUT_MS)
        reply = self._manager.get(request)
        self._pending[reply] = on_done
        reply.finished.connect(lambda: self._finished(reply))
        return _Request(self, reply)

    def _forget(self, reply):
        return self._pending.pop(reply, None)

    def _finished(self, reply):
        on_done = self._forget(reply)
        if on_done is None:  # aborted
            return
        try:
            status = reply.attribute(QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            status = int(status) if status is not None else None
            error = None
            if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
                error = reply.errorString() or "the network request failed"
            body = bytes(reply.readAll().data())
        except Exception:
            log.exception("Reading the network reply failed")
            status, body, error = None, b"", "the network reply could not be read"
        finally:
            reply.deleteLater()
        log.info("GET %s -> %s%s", reply.url().toString(), status, f" ({error})" if error else "")
        on_done(Response(status=status, body=body, error=error))

    def close(self):
        for reply in list(self._pending):
            self._forget(reply)
            try:
                reply.abort()
                reply.deleteLater()
            except Exception:
                pass
        self._manager.deleteLater()
