class NoCacheForAuthenticatedRequestsMiddleware:
    """
    Prevents the browser (or any proxy in between) from caching pages that
    were rendered for a logged-in user.

    Without this, a very common - and very convincing - "sessions/
    notifications are shared between users" bug report turns out to be:
    User A logs out (or User B logs in on the same computer/browser), then
    hits the back button. The browser has User A's dashboard/notifications
    page cached and just replays it from cache without asking the server
    at all, so it *looks* like the new user is seeing the old user's data,
    even though the server-side session and queries were correctly scoped
    the whole time. Marking every authenticated response as non-cacheable
    closes that gap: the back button always has to re-fetch from the
    server, which will render the actual current user (or bounce to
    login if there isn't one).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            response["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response