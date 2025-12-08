import os
from django import template
from django.conf import settings
from PIL import Image, ImageEnhance

register = template.Library()

# --- KONFIGURACJA ---
OPACITY = 0.4        # Przezroczystość: 0.0 (niewidoczne) do 1.0 (pełne krycie). 0.15 to subtelne 15%
TILE_SCALE = 0.15     # Jak duże ma być logo względem szerokości zdjęcia (0.25 = 1/4 szerokości)
SPACING = 75          # Odstęp między kafelkami (w pikselach)
# --------------------

@register.filter(name='add_watermark')
def add_watermark(image_field):
    if not image_field:
        return ""

    try:
        # 1. Ścieżki
        original_path = image_field.path
        filename = os.path.basename(original_path)
        watermarked_dir = os.path.join(settings.MEDIA_ROOT, 'watermarked')
        
        if not os.path.exists(watermarked_dir):
            os.makedirs(watermarked_dir)
            
        watermarked_path = os.path.join(watermarked_dir, filename)
        watermarked_url = f"{settings.MEDIA_URL}watermarked/{filename}"

        # 2. Cache - jeśli plik istnieje, zwracamy go
        if os.path.exists(watermarked_path):
            return watermarked_url

        # 3. Przygotowanie obrazów
        # Otwieramy oryginał i konwertujemy na RGBA (kanał przezroczystości)
        base_image = Image.open(original_path).convert("RGBA")
        
        watermark_path = os.path.join(settings.BASE_DIR, 'static', 'watermark.png')
        if not os.path.exists(watermark_path):
            return image_field.url

        watermark = Image.open(watermark_path).convert("RGBA")

        # 4. Zmniejszanie przezroczystości watermarku
        # Rozdzielamy kanały: R, G, B, Alpha
        r, g, b, alpha = watermark.split()
        # Zmniejszamy wartości w kanale Alpha
        alpha = alpha.point(lambda p: int(p * OPACITY))
        # Składamy z powrotem z nową przezroczystością
        watermark.putalpha(alpha)

        # 5. Skalowanie kafelka
        # Ustalamy szerokość kafelka jako % szerokości zdjęcia głównego
        wm_width = int(base_image.width * TILE_SCALE)
        wm_ratio = watermark.height / watermark.width
        wm_height = int(wm_width * wm_ratio)
        
        # Używamy LANCZOS dla ładnego skalowania
        watermark = watermark.resize((wm_width, wm_height), Image.Resampling.LANCZOS)

        # 6. Kafelkowanie (Tiling)
        # Tworzymy pustą przezroczystą warstwę o rozmiarze zdjęcia
        watermark_layer = Image.new('RGBA', base_image.size, (0,0,0,0))
        
        # Pętle do układania kafelków
        for y in range(0, base_image.height, wm_height + SPACING):
            for x in range(0, base_image.width, wm_width + SPACING):
                # Opcjonalnie: Przesunięcie co drugi rząd (efekt cegły)
                offset_x = 0
                if (y // (wm_height + SPACING)) % 2 == 1:
                    offset_x = (wm_width + SPACING) // 2
                
                # Wklejamy kafelek na warstwę
                # Używamy x - offset_x, żeby kafelki wychodziły poza krawędź po lewej stronie przy przesunięciu
                draw_x = x - offset_x if (y // (wm_height + SPACING)) % 2 == 1 else x
                
                # Żeby wypełnić lukę po lewej przy przesunięciu, można dodać prostą logikę,
                # ale dla prostoty pominęliśmy skomplikowane warunki krawędziowe.
                # Wklejamy na warstwę:
                watermark_layer.paste(watermark, (draw_x, y))
                # Jeśli przesuwamy, doklejamy dodatkowy kafelek na końcu wiersza
                if (y // (wm_height + SPACING)) % 2 == 1:
                     watermark_layer.paste(watermark, (base_image.width - (wm_width//2), y))


        # 7. Nakładanie warstwy z kafelkami na zdjęcie
        # alpha_composite wymaga, aby oba obrazy były RGBA i tego samego rozmiaru
        final_image = Image.alpha_composite(base_image, watermark_layer)

        # 8. Zapis
        final_image.convert("RGB").save(watermarked_path, "JPEG", quality=85)
        
        return watermarked_url

    except Exception as e:
        print(f"Błąd watermarka: {e}")
        return image_field.url