from .models import AuditLog
import traceback

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            body = None
            try:
                body = request.body.decode('utf-8') if request.body else None
            except Exception:
                body = None
            AuditLog.objects.create(
                user=user,
                path=request.path,
                method=request.method,
                status_code=getattr(response, 'status_code', None),
                request_body=body,
            )
        except Exception:
            # ensure middleware never crashes the app
            traceback.print_exc()
        return response
