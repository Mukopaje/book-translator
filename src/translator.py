"""
Translation Module for Book Translator
Uses Google Cloud Translate API for translation
"""

import os
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import translate_v2 as translate


class TextTranslator:
    """Translates Japanese text to English using Google Cloud Translate API"""
    
    def __init__(self):
        """Initialize the translator with Google Cloud Translate API"""
        # Load environment variables from .env file (from project root)
        project_root = Path(__file__).parent.parent.resolve()
        load_dotenv(project_root / '.env')
        
        # Google Cloud Translate uses GOOGLE_APPLICATION_CREDENTIALS env var
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and not os.path.isabs(creds_path):
            # If relative path, make it absolute from project root
            creds_path = str(project_root / creds_path)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
        
        try:
            self.client = translate.Client()
            self.available = True
            print("[OK] Google Translate API initialized")
        except Exception as e:
            print(f"[ERROR] Failed to initialize Google Translate: {e}")
            self.available = False
            self.client = None
    
    def translate_text(self, text: str, context: str = None, source_lang: str = 'ja', target_lang: str = 'en') -> str:
        """
        Translate Japanese text to English
        
        Args:
            text: The Japanese text to translate
            context: Context for the translation (not used by Google Translate, kept for compatibility)
            source_lang: Source language code (default: 'ja' for Japanese)
            target_lang: Target language code (default: 'en' for English)
            
        Returns:
            Translated English text
        """
        if not self.available:
            raise RuntimeError("Google Translate API not available")
        
        if not text or not text.strip():
            return ""
        
        try:
            # Translate using Google Cloud Translate API
            result = self.client.translate(
                text,
                source_language=source_lang,
                target_language=target_lang,
                format_='text'
            )
            
            return result['translatedText']
            
        except Exception as e:
            raise Exception(f"Translation failed: {str(e)}")
    
    def translate_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """
        Translate multiple paragraphs of text
        
        Args:
            paragraphs: List of Japanese text paragraphs
            
        Returns:
            List of translated English paragraphs
        """
        translated = []
        
        for i, paragraph in enumerate(paragraphs):
            print(f"Translating paragraph {i+1}/{len(paragraphs)}...")
            
            try:
                result = self.translate_text(paragraph)
                translated.append(result)
            except Exception as e:
                print(f"Error translating paragraph {i+1}: {str(e)}")
                translated.append(paragraph)  # Keep original if translation fails
        
        return translated
    
    def translate_with_labels(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """
        Translate a dictionary of labeled text (e.g., diagram labels)
        
        Args:
            text_dict: Dictionary with keys as labels and values as Japanese text
            
        Returns:
            Dictionary with same keys and English translations as values
        """
        translated_dict = {}
        
        for label, japanese_text in text_dict.items():
            try:
                translated_dict[label] = self.translate_text(japanese_text)
            except Exception as e:
                print(f"Error translating '{label}': {str(e)}")
                translated_dict[label] = japanese_text  # Keep original if translation fails
        
        return translated_dict
    
    def save_translation(self, original: str, translated: str, output_path: str):
        """
        Save both original and translated text to a file
        
        Args:
            original: Original Japanese text
            translated: Translated English text
            output_path: Path where to save
        """
        content = f"""=== ORIGINAL (Japanese) ===
{original}

=== TRANSLATION (English) ===
{translated}
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Translation saved to {output_path}")


if __name__ == "__main__":
    # Example usage
    try:
        translator = TextTranslator()
        
        if not translator.available:
            print("Google Translate API not available. Check credentials.")
            exit(1)
        
        # Example Japanese text
        sample_japanese = "これはテストです。"
        
        print("Translating sample text...")
        print("Original:", sample_japanese)
        
        translation = translator.translate_text(sample_japanese)
        print("\nTranslation:", translation)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nMake sure you have enabled Google Cloud Translation API")
