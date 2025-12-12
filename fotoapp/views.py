# fotoapp/views.py

import os
import zipfile
import stripe
import io
from PIL import Image, ImageEnhance # ImageEnhance potrzebne do przezroczystości
from django.contrib.staticfiles import finders

from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from .models.session import Session
from .models.photo import Photo
from .utils import decrypt_path, encrypt_path
from .cart import (
    add as cart_add,
    remove as cart_remove,
    count as cart_count,
    _cart as get_cart
)

# Konfiguracja Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# ===============================
#         STRONY GŁÓWNE
# ===============================

def homepage(request):
    return render(request, 'fotoapp/homepage.html')


def oferta(request):
    return render(request, 'fotoapp/oferta.html')


def kontakt(request):
    return render(request, 'fotoapp/kontakt.html')


def check_password(request):
    if request.method == "POST":
        password = request.POST.get('password')
        try:
            session = Session.objects.get(password=password)
            session.access_token = session.generate_new_token()
            session.save()
            return redirect('gallery_view', access_token=session.access_token)
        except Session.DoesNotExist:
            return render(request, 'fotoapp/homepage.html', {'error': 'Nieprawidłowe hasło'})
    return redirect('home')


# ===============================
#            GALERIA
# ===============================

def gallery_view(request, access_token):
    session = get_object_or_404(Session, access_token=access_token)
    photos = session.photos.all()
    request.session['gallery_access'] = True
    for photo in photos:
        photo.token = encrypt_path(photo.image.name)
    return render(request, 'fotoapp/gallery.html', {'session': session, 'photos': photos})


def serve_encrypted_image(request, token):
    """
    Serwuje obraz z SIATKĄ ZNAKÓW WODNYCH (Tiled Watermark).
    """
    try:
        # Sprawdzanie uprawnień sesji (opcjonalne, ale zalecane)
        if not request.session.get('gallery_access'):
             # Jeśli chcesz pozwolić koszykowi działać bez sesji galerii (np. po odświeżeniu),
             # możesz zakomentować poniższą linię, ale zmniejsza to bezpieczeństwo.
             pass 
             # return HttpResponseForbidden("Dostęp zabroniony.")
            
        path = decrypt_path(token)
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        
        if not os.path.isfile(full_path):
            raise FileNotFoundError

        # --- GENEROWANIE SIATKI ZNAKÓW WODNYCH ---
        try:
            # 1. Otwórz zdjęcie główne
            base_image = Image.open(full_path).convert("RGBA")
            
            # 2. Znajdź logo
            watermark_path = finders.find('images/logo.png') # lub logo-inverted.png
            
            if watermark_path:
                watermark = Image.open(watermark_path).convert("RGBA")
                
                # 3. Zmniejsz logo (do kafelkowania - np. 15% szerokości zdjęcia)
                scale_factor = 0.15 
                wm_width = int(base_image.width * scale_factor)
                wm_ratio = watermark.height / watermark.width
                wm_height = int(wm_width * wm_ratio)
                
                # Resize
                watermark = watermark.resize((wm_width, wm_height), Image.Resampling.LANCZOS)
                
                # 4. Zmniejsz przezroczystość logo (żeby nie było zbyt nachalne w siatce)
                # Tworzymy nową warstwę alfa z mniejszą wartością
                alpha = watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(0.3) # 0.3 = 30% widoczności
                watermark.putalpha(alpha)

                # 5. PĘTLA KAFELKOWANIA (Tiling)
                # Obliczamy odstępy (np. logo + 50% marginesu)
                step_x = int(wm_width * 1.5)
                step_y = int(wm_height * 1.5)
                
                # Przesuwamy start trochę, żeby siatka była ładnie rozłożona
                start_x = int(step_x * 0.5)
                start_y = int(step_y * 0.5)

                # Iterujemy po całym obrazku
                for y in range(0, base_image.height, step_y):
                    for x in range(0, base_image.width, step_x):
                        # Opcjonalnie: Przesunięcie co drugi rząd (efekt cegieł)
                        offset_x = 0
                        if (y // step_y) % 2 == 1:
                            offset_x = int(step_x / 2)
                            
                        # Pozycja wklejenia
                        pos_x = x + offset_x
                        pos_y = y
                        
                        # Sprawdź czy nie wychodzimy za bardzo (opcjonalne, paste radzi sobie z cropem)
                        base_image.paste(watermark, (pos_x, pos_y), watermark)

            # 6. Konwersja i zapis do pamięci
            rgb_image = base_image.convert("RGB")
            buffer = io.BytesIO()
            rgb_image.save(buffer, format="JPEG", quality=80) # quality 80 dla szybszego ładowania koszyka
            buffer.seek(0)
            
            return FileResponse(buffer, content_type='image/jpeg')

        except Exception as e:
            # Fallback w razie błędu graficznego - wyślij oryginał (lub placeholder)
            print(f"Watermark Error: {e}")
            return FileResponse(open(full_path, 'rb'), content_type='image/jpeg')

    except Exception:
        raise Http404("Błędny token lub plik nie istnieje")


# ===============================
#         API KOSZYKA
# ===============================

@require_POST
def api_cart_add(request, photo_id: int):
    try:
        p = Photo.objects.get(pk=photo_id)
    except Photo.DoesNotExist:
        raise Http404("Photo not found")

    cart_add(request, photo_id=p.id, price=p.price, qty=1)
    return JsonResponse({"ok": True, "count": cart_count(request)})


@require_POST
def api_cart_remove(request, photo_id: int):
    try:
        p = Photo.objects.get(pk=photo_id)
    except Photo.DoesNotExist:
        raise Http404("Photo not found")

    cart_remove(request, photo_id=p.id, qty=1)
    return JsonResponse({"ok": True, "count": cart_count(request)})


@require_POST
def api_cart_delete(request, photo_id: int):
    cart = get_cart(request)
    cart.pop(str(photo_id), None)
    request.session.modified = True
    return JsonResponse({"ok": True, "count": cart_count(request)})


def api_cart_summary(request):
    cart = get_cart(request)
    if not cart:
        return JsonResponse({"ok": True, "items": [], "total": "0.00", "count": 0})

    ids = [int(pid) for pid in cart.keys()]
    photos = Photo.objects.filter(id__in=ids)
    photos_map = {p.id: p for p in photos}

    items = []
    total = 0.0

    for pid_str, entry in cart.items():
        pid = int(pid_str)
        p = photos_map.get(pid)
        if not p:
            continue
        qty = int(entry.get("qty", 0))
        price = float(entry.get("price", 0))
        line_total = qty * price
        total += line_total

        # Token do obrazka z watermarkiem
        token = encrypt_path(p.image.name)
        thumb_url = request.build_absolute_uri(
            reverse("serve_encrypted_image", args=[token])
        )

        items.append({
            "id": pid,
            "qty": qty,
            "price": f"{price:.2f}",
            "line_total": f"{line_total:.2f}",
            "thumb": thumb_url,
        })

    return JsonResponse({
        "ok": True,
        "items": items,
        "total": f"{total:.2f}",
        "count": sum(i["qty"] for i in cart.values()),
    })


def cart_view(request):
    return render(request, "cart/view.html", {"cart": get_cart(request)})


# ===============================
#      PŁATNOŚCI I ZIP
# ===============================

def create_checkout_session(request):
    cart = get_cart(request)
    if not cart:
        return redirect('home')

    domain = request.build_absolute_uri('/')[:-1] 
    line_items = []
    
    ids = [int(pid) for pid in cart.keys()]
    photos = Photo.objects.filter(id__in=ids)
    photos_map = {p.id: p for p in photos}

    for pid_str, entry in cart.items():
        pid = int(pid_str)
        photo = photos_map.get(pid)
        if not photo:
            continue
        unit_amount = int(float(entry.get('price', 0)) * 100)
        
        line_items.append({
            'price_data': {
                'currency': 'pln',
                'product_data': {
                    'name': f'Zdjęcie #{photo.id}',
                },
                'unit_amount': unit_amount,
            },
            'quantity': 1,
        })

    if not line_items:
        return redirect('home')

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'blik'],
            line_items=line_items,
            mode='payment',
            success_url=domain + reverse('payment_success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain + reverse('home'),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return JsonResponse({'error': str(e)})


def payment_success(request):
    session_id = request.GET.get('session_id')
    customer_email = None

    if session_id:
        try:
            session_details = stripe.checkout.Session.retrieve(session_id)
            if session_details.customer_details:
                customer_email = session_details.customer_details.email
        except Exception as e:
            print(f"Błąd pobierania danych ze Stripe: {e}")

    cart = get_cart(request)
    if not cart:
        return render(request, 'fotoapp/homepage.html', {'error': 'Sesja wygasła lub koszyk jest pusty.'})

    ids = [int(pid) for pid in cart.keys()]
    photos = Photo.objects.filter(id__in=ids)

    if not photos.exists():
        return redirect('home')

    zip_dir = os.path.join(settings.MEDIA_ROOT, 'zips')
    if not os.path.exists(zip_dir):
        os.makedirs(zip_dir)

    session_key = request.session.session_key or 'unknown'
    zip_filename = f"zamowienie_{session_key[:8]}.zip"
    zip_filepath = os.path.join(zip_dir, zip_filename)
    
    zip_relative_url = f"{settings.MEDIA_URL}zips/{zip_filename}"
    zip_absolute_url = request.build_absolute_uri(zip_relative_url)

    # ZIPUJEMY ORYGINAŁY
    try:
        with zipfile.ZipFile(zip_filepath, 'w') as zip_file:
            for photo in photos:
                original_path = photo.image.path 
                if os.path.exists(original_path):
                    zip_file.write(original_path, arcname=os.path.basename(original_path))
    except Exception as e:
        return render(request, 'fotoapp/homepage.html', {'error': 'Wystąpił błąd podczas generowania plików (ZIP).'})

    # WYSYŁKA MAILA
    email_sent = False
    if customer_email:
        try:
            send_mail(
                subject='Twoje zdjęcia - Kilar Fotografia',
                message=f'Dziękujemy za zakup!\n\nTwoje zdjęcia są gotowe do pobrania pod tym linkiem:\n{zip_absolute_url}\n\nPozdrawiamy,\nZespół Kilar Fotografia',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer_email],
                fail_silently=False,
            )
            email_sent = True
        except Exception as e:
            print(f"Błąd wysyłki maila: {e}")

    request.session['cart'] = {}
    request.session.modified = True

    context = {
        'zip_url': zip_relative_url,
        'count': photos.count(),
        'email': customer_email,
        'email_error': not email_sent and customer_email is not None
    }
    return render(request, 'fotoapp/success.html', context)