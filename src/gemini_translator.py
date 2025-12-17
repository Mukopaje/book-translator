"""
Gemini-based Translator for Technical Manuals
Uses Google Gemini 2.5 Flash for intelligent, context-aware translation
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai


class GeminiTranslator:
    """
    Advanced translator using Google Gemini 2.5 Flash
    Provides context-aware translation with proper formatting
    """
    
    def __init__(self, model_name="gemini-2.0-flash"):
        """Initialize Gemini translator"""
        # Load environment variables
        project_root = Path(__file__).parent.parent.resolve()
        load_dotenv(project_root / '.env')
        
        # Get API key
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Initialize model
        try:
            self.model = genai.GenerativeModel(model_name)
            self.available = True
            print(f"[OK] Gemini {model_name} initialized for translation")
        except Exception as e:
            print(f"[ERROR] Failed to initialize Gemini: {e}")
            self.available = False
            self.model = None
    
    def translate_text(self, text: str, context: str = None, source_lang: str = 'ja', target_lang: str = 'en') -> str:
        """
        Translate text using Gemini with intelligent context awareness
        
        Args:
            text: Text to translate
            context: Additional context (e.g., "technical manual", "diagram labels")
            source_lang: Source language (default: 'ja' for Japanese)
            target_lang: Target language (default: 'en' for English)
            
        Returns:
            Translated text
        """
        if not self.available:
            raise RuntimeError("Gemini translator not available")
        
        if not text or not text.strip():
            return ""
        
        # Build prompt for Gemini
        prompt = self._build_translation_prompt(text, context, source_lang, target_lang)
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            raise Exception(f"Gemini translation failed: {str(e)}")
    
    def _build_translation_prompt(self, text: str, context: str, source_lang: str, target_lang: str) -> str:
        """Build optimized prompt for Gemini translation"""
        
        lang_names = {
            'ja': 'Japanese',
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'zh': 'Chinese'
        }
        
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)
        
        context_instruction = ""
        if context and "technical" in context.lower():
            # Extract book context if present
            book_context_str = ""
            if "Book Context:" in context:
                parts = context.split("Book Context:")
                if len(parts) > 1:
                    book_context_str = f"\nBOOK CONTEXT: {parts[1].strip()}\nUse this context to ensure correct technical terminology (e.g. 'Stroke' vs 'Process')."

            context_instruction = f"""
This is from a technical manual. {book_context_str}
Important guidelines:
- Preserve technical terminology accurately
- Maintain numbered sections and figure references (e.g., "Figure 2-3", "(C)", "(D)")
- Keep measurement units and values exact
- Preserve paragraph structure with double line breaks between paragraphs
- Use clear, professional technical English
- Keep page numbers in their original format (e.g., -28-)
- Ignore OCR artifacts like random letters/symbols that don't make sense
- Organize the text into clear, logical paragraphs
- If you see diagram labels or fragmented text, try to organize it coherently
"""
        
        prompt = f"""You are an expert technical translator specializing in {source_name} to {target_name} translation.

{context_instruction}

Translate the following {source_name} text to {target_name}. Return ONLY the translated text, with no explanations or additional commentary.

{source_name} text:
{text}

{target_name} translation:"""
        
        return prompt
    
    def translate_paragraph(self, paragraph_text: str, context: str = "technical manual") -> str:
        """
        Translate a complete paragraph with full context
        Optimized for technical manual paragraphs
        """
        return self.translate_text(paragraph_text, context=context)
    
    def translate_with_layout_analysis(self, paragraphs: list, page_structure: dict = None) -> list:
        """
        Translate multiple paragraphs while preserving document structure
        
        Args:
            paragraphs: List of paragraph texts
            page_structure: Optional dict with layout info (headers, page numbers, etc.)
            
        Returns:
            List of translated paragraphs
        """
        if not self.available:
            raise RuntimeError("Gemini translator not available")
        
        translated = []
        
        for i, para in enumerate(paragraphs):
            if not para.strip():
                translated.append("")
                continue
            
            # Detect special content
            context = "technical manual"
            
            # Page numbers
            if para.strip().startswith('-') and para.strip().endswith('-') and len(para.strip()) < 10:
                # Don't translate page numbers
                translated.append(para)
                continue
            
            # Section headers (usually short, may have parentheses)
            if len(para.strip()) < 50 and ('(' in para or ')' in para or para.isupper()):
                context = "technical manual section header"
            
            # Translate with appropriate context
            try:
                result = self.translate_text(para, context=context)
                translated.append(result)
                
                if i < 3:  # Show progress for first few
                    print(f"    Paragraph {i+1}: {len(para)} chars -> {len(result)} chars")
            
            except Exception as e:
                print(f"  Warning: Translation failed for paragraph {i+1}: {e}")
                translated.append(para)  # Keep original on failure
        
        return translated
    
    def save_translation(self, original: str, translated: str, output_path: str):
        """Save original and translated text"""
        content = f"""=== ORIGINAL (Japanese) ===
{original}

=== TRANSLATION (English) ===
{translated}
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Translation saved to {output_path}")


if __name__ == "__main__":
    # Test the Gemini translator
    try:
        translator = GeminiTranslator()
        
        if not translator.available:
            print("Gemini translator not available. Check API key.")
            exit(1)
        
        # Test translation
        sample_japanese = "これはテストです。技術マニュアルの翻訳を確認しています。"
        
        print("Translating sample text...")
        print("Original:", sample_japanese)
        
        translation = translator.translate_text(sample_japanese, context="technical manual")
        print("\nTranslation:", translation)
        
    except Exception as e:
        print(f"Error: {str(e)}")
