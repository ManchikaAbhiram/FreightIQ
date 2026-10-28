from django.shortcuts import redirect
from django.urls import reverse


class ApprovalMiddleware:
    """Enforce approval and prevent authenticated pages being restored from cache."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Run the view first so every response, including redirects, receives
        # the cache-prevention headers below.
        blocked_response = None
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                profile = request.user.profile
            except Exception:
                profile = None

            allowed = [reverse('logout'), reverse('login'), reverse('register'), reverse('waiting_for_approval')]
            if (
                (not profile or profile.status != 'APPROVED')
                and request.path not in allowed
                and not request.path.startswith('/static/')
                and not request.path.startswith('/media/')
            ):
                from django.contrib import messages
                messages.error(request, 'Your account is not approved for business access yet.')
                blocked_response = redirect('waiting_for_approval')

        response = blocked_response or self.get_response(request)
        # Apply to all HTML/dynamic responses, not just requests where the user
        # is authenticated. This helps prevent browser Back from showing stale
        # protected content after logout or login-state changes.
        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type or response.status_code in (301, 302, 303, 307, 308):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
