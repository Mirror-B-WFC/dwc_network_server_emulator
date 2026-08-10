"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
    Copyright (C) 2014 AdmiralCurtiss
    Copyright (C) 2014 msoucy
    Copyright (C) 2015 Sepalani

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import socket
import BaseHTTPServer
import SocketServer
import os
import traceback

from other import dlc, utils
import dwc_config

logger = dwc_config.get_logger('Dls1Server')


def handle_post(handler, addr, post):
    """Handle unknown path."""
    logger.log(logging.WARNING, "Unknown path request %s from %s:%d!",
               handler.path, *addr)
    handler.send_response(404)
    return None


def handle_download_action(handler, dlc_path, post):
    """Handle unknown download action request."""
    logger.log(logging.WARNING, "Unknown download action: %s", handler.path)
    handler.send_response(200)
    return None


def handle_download_count(handler, dlc_path, post):
    """Handle download count request."""
    ret = dlc.download_count(dlc_path, post)
    handler.send_response(200)
    handler.send_header("Content-type", "text/plain")
    handler.send_header("X-DLS-Host", "http://127.0.0.1/")
    return ret

# TODO Base 64 ?
def handle_download_list(handler, dlc_path, post):
    """Handle download list request."""
    ret = dlc.download_list(dlc_path, post)
    handler.send_response(200)
    handler.send_header("Content-type", "text/plain")
    handler.send_header("X-DLS-Host", "http://127.0.0.1/")
    return ret


def handle_download_contents(handler, dlc_path, post):
    """Handle download contents request."""
    ret = dlc.download_contents(dlc_path, post)

    if ret is None:
        handler.send_response(404)
    else:
        handler.send_response(200)
        handler.send_header("Content-type", "application/x-dsdl")
        handler.send_header("Content-Disposition",
                            'attachment; filename="%s"' % post["contents"])
        handler.send_header("X-DLS-Host", "http://127.0.0.1/")
    return ret


def handle_download(handler, addr, post):
    """Handle download POST request."""
    logger.log(logging.DEBUG, "Download request to %s from %s:%d",
               handler.path, *addr)
    logger.log(logging.DEBUG, "%s", post)

    action = str(post["action"]).lower()
    dlc_dir = os.path.abspath("dlc")
    dlc_path = os.path.abspath(os.path.join("dlc", post["gamecd"]))

    # If the base64-decoded path doesn't exist, fall back to the plain-decoded
    # path that came from qs_to_dict_plain (for any client that doesn't
    # base64-encode its DLS1 POST values).
    if not os.path.exists(dlc_path) and "gamecd_plain" in post:
        fallback = os.path.abspath(os.path.join("dlc", post["gamecd_plain"]))
        if os.path.exists(fallback):
            logger.log(logging.DEBUG, "handle_download: b64 path missing, using plain fallback: %s", fallback)
            post["gamecd"] = post["gamecd_plain"]
            post["rhgamecd"] = post.get("rhgamecd_plain", post["rhgamecd"])
            dlc_path = fallback

    if os.path.commonprefix([dlc_dir, dlc_path]) != dlc_dir:
        logging.log(logging.WARNING,
                    'Attempted directory traversal attack "%s",'
                    ' cancelling.', dlc_path)
        handler.send_response(403)
        return

    command = handler.download_actions.get(action, handle_download_action)
    ret = command(handler, dlc_path, post)

    logger.log(logging.DEBUG, "Download response to %s:%d", *addr)
    return ret


class Dls1HTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Nintendo Dls1 server handler."""

    post_paths = {
        "/download": handle_download
    }

    download_actions = {
        "count": handle_download_count,
        "list": handle_download_list,
        "contents": handle_download_contents,
    }

    def version_string(self):
        return "Nintendo Wii (http)"

    def do_POST(self):
        try:
            length = int(self.headers['content-length'])
            body = self.rfile.read(length)

            # DLS1 clients may use base64 or plain encoded URL values, depending on the sdk version.
            #
            # action/gamecd/rhgamecd/attr1/token/num/offset may all arrive as base64
            #
            # Parse base64 first; also stash plain values as fallback.
            post = utils.qs_to_dict(body)
            plain_post = utils.qs_to_dict_plain(body)
            post["gamecd_plain"] = plain_post.get("gamecd", post.get("gamecd", ""))
            post["rhgamecd_plain"] = plain_post.get("rhgamecd", post.get("rhgamecd", ""))
            client_address = (
                self.headers.get('x-forwarded-for', self.client_address[0]),
                self.client_address[1]
            )
            post['ipaddr'] = client_address[0]

            command = self.post_paths.get(self.path, handle_post)
            ret = command(self, client_address, post)

            if ret is not None:
                self.send_header("Content-Length", str(len(ret)))
            self.end_headers()
            if ret is not None:
                self.wfile.write(ret)
        except:
            logger.log(logging.ERROR, "Exception occurred on POST request!")
            logger.log(logging.ERROR, "%s", traceback.format_exc())


class Dls1HTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Threading HTTP server."""
    pass


class Dls1Server(object):
    def start(self):
        address = dwc_config.get_ip_port('Dls1Server')
        httpd = Dls1HTTPServer(address, Dls1HTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...",
                   *address)
        httpd.serve_forever()


if __name__ == "__main__":
    dls1 = Dls1Server()
    dls1.start()
