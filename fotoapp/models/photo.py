from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import models
from django.utils.html import mark_safe
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
from .session import Session
import os
import sys
from io import BytesIO
from PIL import Image  # Wymagana biblioteka Pillow

# Funkcja generująca dynamiczną ścieżkę dla oryginałów
def session_directory_path(instance, filename):
    session_name_slug = instance.session.name.replace(' ', '_').lower()
    return os.path.join('session_photos', session_name_slug, 'originals', filename)

# Funkcja generująca dynamiczną ścieżkę dla zdjęć z watermarkiem
def watermarked_directory_path(instance, filename):
    session_name_slug = instance.session.name.replace(' ', '_').lower()
    return os.path.join('session_photos', session_name_slug, 'watermarked', filename)

class Photo(models.Model):
    session = models.ForeignKey(Session, related_name='photos', on_delete=models.CASCADE)
    # Oryginalny plik (wysoka jakość)
    image = models.ImageField(upload_to=session_directory_path, verbose_name="Oryginał")
    # Plik z watermarkiem (do wyświetlania w galerii)
    watermarked_image = models.ImageField(upload_to=watermarked_directory_path, blank=True, null=True, verbose_name="Wersja z logo")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Cena zdjęcia w PLN")

    def __str__(self):
        return f"Photo {self.id} for {self.session.name}"

    def image_tag(self):
        # W panelu admina pokazujemy wersję z watermarkiem jeśli istnieje, jeśli nie to oryginał
        img_url = self.watermarked_image.url if self.watermarked_image else self.image.url
        return mark_safe(f'<img src="{img_url}" style="max-height: 100px; max-width: 100px;" />')
    
    image_tag.short_description = 'Podgląd'

    def save(self, *args, **kwargs):
        # Jeśli dodano nowe zdjęcie (self.image), a nie ma jeszcze watermarka
        if self.image and not self.watermarked_image:
            self.apply_watermark()
            
        super().save(*args, **kwargs)

    def apply_watermark(self):
        """Generuje wersję zdjęcia z nałożonym logo (watermark.png)."""
        if not self.image:
            return

        # 1. Otwórz oryginał
        img = Image.open(self.image)
        
        # Obsługa formatów z przezroczystością (np. PNG) i bez (JPEG)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 2. Ścieżka do logo (watermarka)
        # Zakładamy, że plik nazywa się 'watermark.png' i jest w static/images/
        watermark_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')

        try:
            watermark = Image.open(watermark_path).convert("RGBA")
        except FileNotFoundError:
            # Jeśli nie ma pliku watermark.png, po prostu przerwij tworzenie watermarka, ale nie wywalaj błędu
            print(f"BŁĄD: Nie znaleziono pliku logo pod ścieżką: {watermark_path}")
            return

        # 3. Skalowanie logo
        # Logo ma zajmować np. 30% szerokości zdjęcia
        target_width = int(img.width * 0.30)
        aspect_ratio = watermark.width / watermark.height
        target_height = int(target_width / aspect_ratio)
        
        watermark = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # 4. Pozycjonowanie (Środek zdjęcia) 
        # Możesz zmienić na prawy dolny róg zmieniając x i y
        x = (img.width - target_width) // 2
        y = (img.height - target_height) // 2
        
        # 5. Nałożenie logo (używamy watermarka jako maski dla samego siebie, aby zachować przezroczystość)
        img.paste(watermark, (x, y), watermark)

        # 6. Konwersja z powrotem do RGB (żeby zapisać jako JPG)
        final_img = img.convert('RGB')

        # 7. Zapis do pamięci (BytesIO) zamiast na dysk
        output = BytesIO()
        final_img.save(output, format='JPEG', quality=85)
        output.seek(0)

        # 8. Przypisanie do pola watermarked_image
        file_name = os.path.basename(self.image.name)
        watermarked_name = f"watermarked_{file_name}"
        
        self.watermarked_image = InMemoryUploadedFile(
            output,
            'ImageField',
            watermarked_name,
            'image/jpeg',
            sys.getsizeof(output),
            None
        )

@receiver(post_delete, sender=Photo)
def photo_delete(sender, instance, **kwargs):
    # Usuń oryginał
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)
    
    # Usuń wersję z watermarkiem
    if instance.watermarked_image:
        if os.path.isfile(instance.watermarked_image.path):
            os.remove(instance.watermarked_image.path)