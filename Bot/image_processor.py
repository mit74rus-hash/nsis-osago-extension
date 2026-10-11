import os
from PIL import Image, ImageEnhance

def preprocess_captcha(image_path):
    try:
        # Открываем изображение и конвертируем в оттенки серого
        img = Image.open(image_path).convert('L')
        
        # Увеличиваем картинку в 4 раза для лучшей точности Tesseract
        new_width = img.width * 4
        new_height = img.height * 4
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Немного повышаем контраст, чтобы буквы были четче
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Сохраняем обработанное изображение
        processed_path = "captcha_processed.png"
        img.save(processed_path)
        return processed_path
    except Exception as e:
        print(f"⚠️ Предупреждение при обработке картинки: {e}")
        return image_path