"""
Main Orchestrator for Book Translator
Coordinates the entire translation pipeline
"""

import argparse
import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from layout_analysis import LayoutAnalyzer
from ocr_extractor import TextExtractor
from translator import TextTranslator
from gemini_translator import GeminiTranslator
from text_overlay import TextOverlay
from pdf_reconstructor import PDFPageReconstructor
from smart_layout_reconstructor import SmartLayoutReconstructor
from diagram_translator import DiagramTranslator


class BookTranslator:
    """Main orchestrator for the book translation pipeline"""
    
    def __init__(self, image_path: str, output_dir: str = "output", book_context: str = None):
        """
        Initialize the book translator
        
        Args:
            image_path: Path to the input image
            output_dir: Directory for output files
            book_context: Optional global context about the book (e.g. "4-stroke engine manual")
        """
        self.image_path = image_path
        self.output_dir = output_dir
        self.page_name = Path(image_path).stem
        self.book_context = book_context
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize components
        self.text_extractor = TextExtractor()
        
        # Try Gemini first, fall back to Google Translate
        try:
            self.translator = GeminiTranslator()
            print("[OK] Using Gemini 2.5 Flash for intelligent translation")
        except Exception as e:
            print(f"[INFO] Gemini not available ({e}), using Google Translate")
            self.translator = TextTranslator()
        
        self.layout_analyzer = LayoutAnalyzer(image_path)
    
    def process_page(self, verbose: bool = True) -> dict:
        """
        Process a single page through the complete pipeline
        
        Args:
            verbose: Print progress messages
            
        Returns:
            Dictionary with results from each step
        """
        results = {
            'image_path': self.image_path,
            'page_name': self.page_name,
            'steps': {}
        }
        
        try:
            # Step 1: Layout Analysis
            if verbose:
                print(f"\n[1/6] Analyzing page layout...")
            regions = self.layout_analyzer.detect_text_regions()
            results['steps']['layout_analysis'] = {
                'success': True,
                'regions_found': len(regions)
            }
            if verbose:
                print(f"  + Found {len(regions)} regions")
            
            # Step 2: OCR Text Extraction
            if verbose:
                print(f"\n[2/6] Extracting Japanese text...")
            japanese_text = self.text_extractor.extract_text(
                self.image_path, 
                language='jpn'
            )
            results['steps']['ocr_extraction'] = {
                'success': True,
                'text_length': len(japanese_text),
                'preview': japanese_text[:100] + "..." if len(japanese_text) > 100 else japanese_text
            }
            if verbose:
                print(f"  + Extracted {len(japanese_text)} characters")
            
            # Step 3: Translation
            if verbose:
                print(f"\n[3/6] Translating to English...")
            
            # Combine global book context with page context
            translation_context = "technical manual"
            if self.book_context:
                translation_context = f"{translation_context}. Book Context: {self.book_context}"
                
            english_text = self.translator.translate_text(
                japanese_text,
                context=translation_context
            )
            results['steps']['translation'] = {
                'success': True,
                'text_length': len(english_text),
                'preview': english_text[:100] + "..." if len(english_text) > 100 else english_text
            }
            if verbose:
                print(f"  + Translation complete ({len(english_text)} characters)")
            
            # Step 4: Create Clean PDF with Smart Layout
            if verbose:
                print(f"\n[4/6] Creating clean translated PDF with smart layout...")
            try:
                # Use smart layout reconstructor
                smart_reconstructor = SmartLayoutReconstructor(self.image_path)
                pdf_path = f"{self.output_dir}/{self.page_name}_translated.pdf"
                
                # Get text boxes with Japanese text (not translated yet)
                from google_ocr import GoogleOCR
                ocr = GoogleOCR()
                ocr_result = ocr.extract_text_with_boxes(self.image_path)
                
                # Add Japanese text to boxes
                text_boxes = []
                for box in ocr_result['text_boxes']:
                    if box['text'].strip():
                        text_boxes.append({
                            'x': box['x'],
                            'y': box['y'],
                            'w': box['w'],
                            'h': box['h'],
                            'text': box['text'],
                            'translation': ''
                        })
                
                # Analyze layout to find diagrams
                # Use the existing smart_reconstructor instance instead of creating a new one
                # or re-importing the class which causes UnboundLocalError
                temp_reconstructor = SmartLayoutReconstructor(self.image_path)
                layout = temp_reconstructor._analyze_layout_structure(text_boxes)
                diagram_regions = layout.get('diagram_regions', [])
                
                if verbose and diagram_regions:
                    print(f"  + Found {len(diagram_regions)} diagram region(s)")
                
                # Step 4b: Translate diagrams if found
                translated_diagrams = None
                if diagram_regions:
                    if verbose:
                        print(f"\n[4b/6] Translating diagram labels...")
                    # Use enhanced processing mode for crisp diagrams with
                    # a clean white background.
                    diagram_translator = DiagramTranslator(processing_mode="enhanced")
                    diagram_output_dir = f"{self.output_dir}/diagrams"
                    translated_diagrams = diagram_translator.process_diagrams(
                        self.image_path,
                        diagram_regions,
                        self.translator,
                        diagram_output_dir,
                        book_context=self.book_context
                    )
                    if verbose:
                        print(f"  + Translated {len(translated_diagrams)} diagram(s)")
                
                # Create the PDF with smart layout (pass full page Japanese text for better translation)
                smart_reconstructor.reconstruct_pdf(
                    text_boxes, 
                    pdf_path, 
                    translator=self.translator,
                    full_page_japanese=japanese_text,  # Use the full extracted text
                    translated_diagrams=translated_diagrams,  # Pass translated diagrams
                    book_context=self.book_context
                )
                
                results['steps']['pdf_creation'] = {
                    'success': True,
                    'output_file': f"{self.page_name}_translated.pdf",
                    'diagrams_translated': len(translated_diagrams) if translated_diagrams else 0
                }
                if verbose:
                    print(f"  + Smart layout PDF created: {pdf_path}")

                # Step 4c: Create Preview Image (Disabled per user request)
                # if verbose:
                #     print(f"\n[4c/6] Creating preview image...")
                # try:
                #     preview_path = f"{self.output_dir}/{self.page_name}_translated.jpg"
                #     overlay = TextOverlay(self.image_path)
                #     # Use the existing translator
                #     overlay.overlay_boxes_with_translation(self.translator, output_path=preview_path)
                #     
                #     if verbose:
                #         print(f"  + Preview image created: {preview_path}")
                # except Exception as e:
                #     print(f"  ! Preview image creation failed: {e}")
                #     # Don't fail the whole process for a preview
                    
            except Exception as e:
                results['steps']['pdf_creation'] = {
                    'success': False,
                    'error': str(e)
                }
                if verbose:
                    print(f"  ! PDF creation failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Propagate error to main result if PDF creation is critical
                # For now, we'll consider it a partial success but log it clearly
                results['warnings'] = results.get('warnings', []) + [f"PDF creation failed: {e}"]

            
            # Step 5: Save Results
            if verbose:
                print(f"\n[5/6] Saving translation results...")
            
            # Save Japanese text
            self.text_extractor.save_ocr_results(
                japanese_text,
                f"{self.output_dir}/{self.page_name}_japanese.txt"
            )
            
            # Save translation
            self.translator.save_translation(
                japanese_text,
                english_text,
                f"{self.output_dir}/{self.page_name}_translation.txt"
            )
            
            results['steps']['save_results'] = {
                'success': True,
                'files_saved': [
                    f"{self.page_name}_japanese.txt",
                    f"{self.page_name}_translation.txt",
                    f"{self.page_name}_translated.pdf"
                ]
            }
            
            if verbose:
                print(f"  + Results saved to {self.output_dir}/")
            
            # Final summary
            if verbose:
                print(f"\n{'='*60}")
                print(f"[SUCCESS] Page Processing Complete!")
                print(f"{'='*60}")
                print(f"Japanese text: {len(japanese_text)} characters")
                print(f"English text: {len(english_text)} characters")
                print(f"Regions processed: {len(regions)}")
                print(f"Output directory: {self.output_dir}/")
            
            results['success'] = True
            
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            if verbose:
                print(f"\n[ERROR] {str(e)}")
        
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Book Translator - Translate Japanese technical manuals to English"
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to input image'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='output',
        help='Output directory (default: output)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress messages'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Create translator and process
    translator = BookTranslator(args.input, args.output)
    results = translator.process_page(verbose=not args.quiet)
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)


if __name__ == "__main__":
    main()
