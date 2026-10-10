import os
from PIL import Image

def preprocess_captcha(image_path):
    try:
        img = Image.open(image_path).convert('L') # Оттенки серого
        
        # Увеличиваем картинку в 2 раза для точности Tesseract
        img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
        
        # Превращаем серый шум в идеально белый фон
        img = img.point(lambda x: 0 if x < 140 else 255, '1')
        
        processed_path = "captcha_processed.png"
        img.save(processed_path)
        return processed_path
    except Exception as e:
        print(f"⚠️ Предупреждение при обработке картинки: {e}")
        return image_path
