from django.middleware.common import CommonMiddleware

from core.exceptions import is_api_request, trailing_slash_response


# For a path that only exists with a trailing slash, Django redirects. The redirect drops the
# body of a POST, PUT, PATCH or DELETE, and with DEBUG it raises an error page instead. Under
# /api/ the client gets a JSON error with the right path; the admin keeps the redirect.
class ApiCommonMiddleware(CommonMiddleware):
    def process_response(self, request, response):
        if self.is_api_route_missing_its_slash(request, response):
            path_with_slash = request.get_full_path(force_append_slash=True)
            return trailing_slash_response(path_with_slash)
        return super().process_response(request, response)

    def is_api_route_missing_its_slash(self, request, response):
        return (
            response.status_code == 404
            and is_api_request(request)
            and self.should_redirect_with_slash(request)
        )
