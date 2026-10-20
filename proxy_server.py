from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.parse
import json
from pathlib import Path

class ProxyHTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api'):
            self.proxy_request()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api'):
            self.proxy_request()
        else:
            self.send_response(404)
            self.end_headers()

    def proxy_request(self):
        try:
            # Forward to backend
            backend_url = f"http://localhost:8888{self.path}"
            headers = {
                'Content-Type': 'application/json',
            }

            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                req = urllib.request.Request(backend_url, data=post_data, headers=headers, method='POST')
            else:
                req = urllib.request.Request(backend_url, headers=headers, method='GET')

            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.headers.items():
                    if header.lower() not in ['content-encoding', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

def run():
    server_address = ('', 3000)
    httpd = HTTPServer(server_address, ProxyHTTPRequestHandler)
    print('Proxy server running on http://localhost:3000')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
