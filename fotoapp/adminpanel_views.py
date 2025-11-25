from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from .models.session import Session
from .models.photo import Photo

@login_required
def dashboard(request):
    return render(request, "adminpanel/dashboard.html")

# --- SESJE ---
@login_required
def session_list(request):
    sessions = Session.objects.all().order_by("-created_at")
    return render(request, "adminpanel/session_list.html", {"sessions": sessions})

@login_required
def session_form(request, id=None):
    """
    id=None -> tworzenie nowej sesji
    id=int -> edycja istniejącej sesji
    """
    session = None
    if id:
        session = get_object_or_404(Session, id=id)

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        password = request.POST.get("password")

        if session:
            # Edycja istniejącej sesji
            session.name = name
            session.description = description
            session.password = password
            session.save()
            messages.success(request, "Zmiany w sesji zapisane!")
        else:
            # Tworzenie nowej sesji
            session = Session.objects.create(
                name=name,
                description=description,
                password=password
            )
            messages.success(request, "Nowa sesja została utworzona!")
            # Po utworzeniu nowej sesji od razu redirect do edycji
            return redirect('panel_session_edit', id=session.id)

    # Pobieranie istniejących zdjęć tylko jeśli sesja istnieje
    photos = session.photos.all() if session else []

    return render(request, "adminpanel/session_form.html", {
        "session": session,
        "photos": photos
    })

@login_required
def session_delete(request, id):
    session = get_object_or_404(Session, id=id)
    session.delete()
    return redirect("panel_sessions")

# --- ZDJĘCIA ---
@login_required
def session_photos(request, id):
    session = get_object_or_404(Session, id=id)
    photos = session.photos.all().order_by("-id")
    return render(request, "adminpanel/session_photos.html", {"session": session, "photos": photos})

@login_required
def session_photos_upload(request, id):
    session = get_object_or_404(Session, id=id)
    if request.method == "POST":
        files = request.FILES.getlist("images")
        if not files:
            return HttpResponseBadRequest("Nie przesłano plików")
        for f in files:
            Photo.objects.create(session=session, image=f)
        photos = session.photos.all().order_by("-id")
        return render(request, "adminpanel/partials/photo_grid.html", {"photos": photos})
    return HttpResponseBadRequest("Invalid request")

@login_required
def set_cover_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    session = photo.session
    session.cover_photo = photo
    session.save()
    photos = session.photos.all()
    html = render(request, "adminpanel/partials/photo_grid.html", {"photos": photos}).content.decode('utf-8')
    return JsonResponse({"html": html})

@login_required
def photo_delete(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    session = photo.session
    photo.delete()
    photos = session.photos.all()
    html = render(request, "adminpanel/partials/photo_grid.html", {"photos": photos}).content.decode('utf-8')
    return JsonResponse({"html": html})
