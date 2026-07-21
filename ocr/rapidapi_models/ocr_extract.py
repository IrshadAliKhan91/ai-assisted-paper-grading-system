"""
OCR Extract Text Model
General purpose OCR
"""
import json
from pathlib import Path


class OCRExtractText:
    """General OCR using OCR Extract Text API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.name = "OCR-Extract"
        self.host = "ocr-extract-text.p.rapidapi.com"
    
    def extract_text(self, image_path):
        """Extract text from image"""
        try:
            import requests
        except ImportError:
            return {"error": "requests library required"}
        
        try:
            ext = Path(image_path).suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            
            files = {'image': (Path(image_path).name, open(image_path, 'rb'), mime_type)}
            
            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.host
            }
            
            url = f"https://{self.host}/ocr"
            response = requests.post(url, files=files, headers=headers)
            
            if response.status_code != 200:
                return {
                    'error': f'Status {response.status_code}',
                    'model': self.name
                }
            
            result = response.json()
            
            return {
                'model': self.name,
                'text': result.get('text', result.get('data', {}).get('text', '')),
                'raw_response': result
            }
        except Exception as e:
            return {'error': str(e), 'model': self.name}
