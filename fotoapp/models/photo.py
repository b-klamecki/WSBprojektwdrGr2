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
from PIL import Image

def session_directory_path(instance, filename):
    session_name_slug = instance.session.name.replace(' ', '_').lower()
    return os.path.join('session_photos', session_name_slug, 'originals', filename)

def watermarked_directory_path(instance, filename):
    session_name_slug = instance.session.name.replace(' ', '_').lower()
    return os.path.join('session_photos', session_name_slug, 'watermarked', filename)

class Photo(models.Model):
    session = models.ForeignKey(Session, related_name='photos', on_delete=models.CASCADE)
    
    # ilosc znakow pod dlugie sciezki plikow
    image = models.ImageField(
        upload_to=session_directory_path, 
        verbose_name="Oryginał",
        max_length=500  
    )
    
    watermarked_image = models.ImageField(
        upload_to=watermarked_directory_path, 
        blank=True, 
        null=True, 
        verbose_name="Wersja z logo",
        max_length=500
    )
    
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Cena zdjęcia w PLN")

    def __str__(self):
        return f"Photo {self.id} for {self.session.name}"

    def image_tag(self):
        img_url = self.watermarked_image.url if self.watermarked_image else self.image.url
        return mark_safe(f'<img src="{img_url}" style="max-height: 100px; max-width: 100px;" />')
    
    image_tag.short_description = 'Podgląd'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def apply_watermark(self):
        """Generuje wersję zdjęcia z nałożonym logo (watermark.png)."""
        if not self.image:
            return

        img = Image.open(self.image)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        watermark_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')

        try:
            watermark = Image.open(watermark_path).convert("RGBA")
        except FileNotFoundError:
            print(f"BŁĄD: Nie znaleziono pliku logo pod ścieżką: {watermark_path}")
            return

        target_width = int(img.width * 0.30)
        aspect_ratio = watermark.width / watermark.height
        target_height = int(target_width / aspect_ratio)
        watermark = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)

        x = (img.width - target_width) // 2
        y = (img.height - target_height) // 2
        img.paste(watermark, (x, y), watermark)

        final_img = img.convert('RGB')
        output = BytesIO()
        final_img.save(output, format='JPEG', quality=85)
        output.seek(0)

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
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)
    
    if instance.watermarked_image:
        if os.path.isfile(instance.watermarked_image.path):
            os.remove(instance.watermarked_image.path)