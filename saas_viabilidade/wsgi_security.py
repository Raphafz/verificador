"""Wrapper WSGI — remove header Server (runserver e gunicorn)."""


def strip_server_header_wsgi(get_response):
    def middleware(environ, start_response):
        def custom_start_response(status, response_headers, exc_info=None):
            filtered = [
                (name, value)
                for name, value in response_headers
                if name.lower() != "server"
            ]
            return start_response(status, filtered, exc_info)

        return get_response(environ, custom_start_response)

    return middleware
