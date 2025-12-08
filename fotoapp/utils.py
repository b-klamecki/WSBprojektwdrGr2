# fotoapp/utils.py
import os
import traceback
import base64
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# CZĘŚĆ 1: SZYFROWANIE ŚCIEŻEK (Przywrócone)
# ==========================================

def encrypt_path(path):
    """
    Koduje ścieżkę do formatu bezpiecznego dla URL (base64).
    """
    return base64.urlsafe_b64encode(path.encode()).decode()

def decrypt_path(encoded_path):
    """
    Odkodowuje ścieżkę z URL.
    """
    return base64.urlsafe_b64decode(encoded_path.encode()).decode()


# ==========================================
# CZĘŚĆ 2: WATERMARK I ZAPIS (Nowe)
# ==========================================

def save_photos(uploaded_file, filename):
    """
    Zapisuje zdjęcie oryginalne i z watermarkiem.
    Wypisuje błędy w konsoli (terminalu), jeśli coś pójdzie nie tak.
    """
    print(f"--- ROZPOCZYNAM PRZETWARZANIE: {filename} ---")

    # 1. Sprawdzenie czy MEDIA_ROOT jest ustawiony
    if not settings.MEDIA_ROOT:
        print("BŁĄD: MEDIA_ROOT nie jest ustawiony w settings.py!")
        return None

    # 2. Tworzenie folderów
    original_dir = os.path.join(settings.MEDIA_ROOT, 'originals')
    watermarked_dir = os.path.join(settings.MEDIA_ROOT, 'watermarked')

    try:
        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(watermarked_dir, exist_ok=True)
    except Exception as e:
        print(f"BŁĄD przy tworzeniu folderów: {e}")
        return None

    original_path = os.path.join(original_dir, filename)
    watermarked_path = os.path.join(watermarked_dir, filename)

    try:
        # 3. Otwieramy i zapisujemy ORYGINAŁ
        image = Image.open(uploaded_file)
        
        # Konwersja na RGB (jeśli ktoś wrzucił PNG z przezroczystością)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        image.save(original_path, quality=100)
        print(f"--> Zapisano oryginał: {original_path}")

        # 4. Tworzymy WATERMARK
        wm_image = image.copy().convert("RGBA")
        
        # Warstwa tekstowa
        txt_layer = Image.new("RGBA", wm_image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Tekst i font
        text = "FOTOAPP DEMO"
        font = ImageFont.load_default() 
        
        # Obliczanie pozycji (metoda bezpieczna dla wszystkich wersji Pillow)
        width, height = wm_image.size
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)
        
        x = (width - text_width) / 2
        y = (height - text_height) / 2

        # Rysujemy tekst
        draw.text((x, y), text, fill=(255, 255, 255, 128), font=font)
        
        # Łączymy warstwy i konwertujemy na RGB
        final_wm = Image.alpha_composite(wm_image, txt_layer)
        final_wm = final_wm.convert("RGB")

        # 5. Zapisujemy WATERMARK
        final_wm.save(watermarked_path, quality=85)
        print(f"--> Zapisano watermark: {watermarked_path}")
        
        print("--- SUKCES ---")
        return filename

    except Exception as e:
        print("\n!!! WYSTĄPIŁ BŁĄD W UTILS.PY !!!")
        print(f"Treść błędu: {e}")
        traceback.print_exc() 
        return None