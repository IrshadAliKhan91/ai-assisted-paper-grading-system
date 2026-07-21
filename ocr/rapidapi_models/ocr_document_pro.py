"""
OCR Document Pro Model
Advanced document OCR
"""
import json
from pathlib import Path


class OCRDocumentPro:
    """Document OCR using OCR Document Pro API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.name = "OCR-Document-Pro"
        self.host = "ocr-document-pro.p.rapidapi.com"
    
    def extract_text(self, image_path):
        """Extract text from image"""
        try:
            import requests
        except ImportError:
            return {"error": "requests library required"}
        
        try:
            ext = Path(image_path).suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            
            files = {'file': (Path(image_path).name, open(image_path, 'rb'), mime_type)}
            data = {
                'barcode': 'false',
                'textPage': 'false',
                'boundingBoxObject': 'false'
            }
            
            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.host
            }
            
            url = f"https://{self.host}/extract"
            response = requests.post(url, files=files, data=data, headers=headers)
            
            if response.status_code != 200:
                return {
                    'error': f'Status {response.status_code}',
                    'model': self.name
                }
            
            result = response.json()
            
            text = result.get('text', '')
            if not text and 'pages' in result:
                text = '\n'.join([page.get('text', '') for page in result['pages']])
            
            return {
                'model': self.name,
                'text': text,
                'raw_response': result
            }
            
        except Exception as e:
            return {'error': str(e), 'model': self.name}
