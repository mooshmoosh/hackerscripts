#!/usr/bin/python3

from http.server import HTTPServer, SimpleHTTPRequestHandler

class CustomRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        return super().end_headers()

server_address = ('', 8000)
httpd = HTTPServer(server_address, CustomRequestHandler)
print("Listening on port 8000")
httpd.serve_forever()
