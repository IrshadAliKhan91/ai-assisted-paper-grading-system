"""
Pen-to-Print Handwriting OCR Model
Specialized for handwritten text
"""
import json
from pathlib import Path


class PenToPrintOCR:
    """Handwriting OCR using Pen-to-Print API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.name = "Pen-to-Print"
        self.url = "https://pen-to-print-handwriting-ocr.p.rapidapi.com/recognize/"
    
    def extract_text(self, image_path):
        """Extract handwritten text from image"""
        try:
            import requests
        except ImportError:
            return {"error": "requests library required: pip install requests"}
        
        ext = Path(image_path).suffix.lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"
        
        files = {'srcImg': (Path(image_path).name, open(image_path, 'rb'), mime_type)}
        data = {'Session': 'string'}
        headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': "pen-to-print-handwriting-ocr.p.rapidapi.com"
        }
        
        response = requests.post(self.url, files=files, data=data, headers=headers)
        result = response.json()
        
        return {
            'model': self.name,
            'text': result.get('value', ''),
            'raw_response': result
        }
