from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache


def home(request):
    if request.user.is_authenticated:
        return redirect("research_objects:list")
    return render(request, "core/home.html")


@never_cache
def liveness(request):
    return JsonResponse({"status": "ok", "service": "web"})


@never_cache
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {"status": "unavailable", "database": "unavailable"},
            status=503,
        )

    return JsonResponse({"status": "ok", "database": "ok"})
