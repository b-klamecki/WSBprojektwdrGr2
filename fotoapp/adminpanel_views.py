from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
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
def session_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        password = request.POST.get("password")

        session = Session.objects.create(
            name=name,
            description=description,
            password=password
        )

        if request.FILES.getlist("images"):
            for img in request.FILES.getlist("images"):
                Photo.objects.create(session=session, image=img)

        messages.success(request, "Nowa sesja została utworzona!")
        return redirect('panel_session_edit_photos', id=session.id)

    return render(request, "adminpanel/session_form.html")

@login_required
def session_edit_photos(request, id):
    session = get_object_or_404(Session, id=id)
    photos = session.photos.all().order_by("-id")

    # Zapis danych sesji
    if request.method == "POST" and "save_session" in request.POST:
        session.name = request.POST.get("name")
        session.password = request.POST.get("password", session.password)
        session.description = request.POST.get("description", "")
        session.save()
        return redirect("panel_session_edit_photos", id=session.id)

    return render(request, "adminpanel/session_edit_photos.html", {
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
    return redirect("panel_session_photos", id=session.id)

@login_required
def photo_delete(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    session_id = photo.session.id
    photo.delete()
    return redirect("panel_session_photos", id=session_id)
