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
from agents.table_agent import TableAgent
from agents.chart_agent import ChartAgent
from agents.diagram_agent import DiagramAgent
from artifacts.schemas import artifacts_to_dict


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
            # Step 1: Preliminary OCR and Layout Analysis
            if verbose:
                print(f"\n[1/6] Extracting text and analyzing page layout...")
            
            from google_ocr import GoogleOCR
            ocr = GoogleOCR()
            ocr_result = ocr.extract_text_with_boxes(self.image_path)
            text_boxes = ocr_result.get('text_boxes', [])
            
            # Use smart reconstructor to identify diagram/table regions early
            smart_reconstructor = SmartLayoutReconstructor(self.image_path)
            layout = smart_reconstructor._analyze_layout_structure(text_boxes)
            diagram_regions = layout.get('diagram_regions', [])
            
            # Filter out diagram text to build the "Cleaned" prose for translation
            cleaned_japanese_list = []
            for box in text_boxes:
                inside_any_diagram = False
                for region in diagram_regions:
                    if (box['x'] >= region['x'] - 5 and 
                        box['y'] >= region['y'] - 5 and 
                        box['x'] + box['w'] <= region['x'] + region['w'] + 5 and 
                        box['y'] + box['h'] <= region['y'] + region['h'] + 5):
                        inside_any_diagram = True
                        break
                if not inside_any_diagram and box.get('text'):
                    cleaned_japanese_list.append(box['text'])
            
            japanese_text = "\n".join(cleaned_japanese_list)
            
            if verbose:
                print(f"  + Found {len(diagram_regions)} diagram region(s)")
                print(f"  + Extracted {len(japanese_text)} characters for prose translation")

            # Step 2: Translation with Context
            if verbose:
                print(f"\n[2/6] Translating cleaned prose to English...")
            
            translation_context = "technical manual"
            if self.book_context:
                translation_context = f"{translation_context}. Book Context: {self.book_context}"
                
            english_text = self.translator.translate_text(
                japanese_text,
                context=translation_context
            )
            
            if verbose:
                print(f"  + Translation complete ({len(english_text)} characters)")
            
            # Step 4: Create Clean PDF with Smart Layout
            if verbose:
                print(f"\n[4/6] Creating clean translated PDF with smart layout...")
            
            # Use the layout we already computed
            # pdf_path and smart_reconstructor are already set up
            pdf_path = f"{self.output_dir}/{self.page_name}_translated.pdf"
            
            # Simplified text box construction since we already have text_boxes from OCR
            # Just add empty translation strings to them for the reconstructor
            for box in text_boxes:
                box['translation'] = ''
            
            # 4a: Run artifact agents (MVP: stubs return empty for tables/charts)
            if verbose:
                print(f"  + Running artifact agents (tables/charts/diagrams)...")
            
            import traceback
            try:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
                import time
                
                def run_table_detection():
                    table_agent = TableAgent()
                    chart_agent = ChartAgent()
                    
                    # Filter out boxes that are inside diagrams to avoid false positive tables
                    non_diagram_boxes = []
                    for box in text_boxes:
                        inside_diagram = False
                        for region in diagram_regions:
                            # Simple hit test with 5px tolerance
                            if (box['x'] >= region['x'] - 5 and 
                                box['y'] >= region['y'] - 5 and 
                                box['x'] + box['w'] <= region['x'] + region['w'] + 5 and 
                                box['y'] + box['h'] <= region['y'] + region['h'] + 5):
                                inside_diagram = True
                                break
                        if not inside_diagram:
                            non_diagram_boxes.append(box)
                    
                    tables = table_agent.detect_and_extract(self.image_path, non_diagram_boxes, self.translator, self.book_context)
                    charts = chart_agent.from_tables(tables)
                    return tables, charts
                
                # Run with 90 second timeout
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_table_detection)
                    try:
                        tables, charts = future.result(timeout=90)
                    except FutureTimeout:
                        if verbose:
                            print(f"    ! Table detection timed out (>90s), setting tables and charts to empty lists.")
                        tables, charts = [], []
                if verbose:
                    print(f"    + Found {len(tables)} tables and {len(charts)} charts.")
                    for i, t in enumerate(tables):
                        print(f"      [Table {i}] {t.id} rows={t.rows} cols={t.cols} bbox={t.bbox.x},{t.bbox.y}")
                    
            except Exception as e:
                if verbose:
                    print(f"    ! Artifact agent error (tables/charts): {e}")
                    print(f"    ! Full stack trace:\n{traceback.format_exc()}")
                tables, charts = [], []
            
            if verbose:
                print(f"  + Artifact detection finished, moving on to diagram translation...")

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
            
            # Normalize diagram artifacts for downstream use (not yet used in PDF composer)
            try:
                diagram_artifacts = DiagramAgent().from_translated_diagrams(translated_diagrams)
            except Exception as e:
                if verbose:
                    print(f"    ! Diagram artifact normalization error: {e}")
                diagram_artifacts = []
            
            # Split previously translated prose into paragraphs
            translated_paragraphs = english_text.split('\n\n')
            
            # Use Gemini to organize paragraphs for better layout (if available)
            if hasattr(self.translator, 'organize_paragraphs') and hasattr(self.translator, 'available') and self.translator.available:
                try:
                    if verbose:
                        print(f"\n[3/6] Organizing paragraphs with Gemini for better layout...")
                    translated_paragraphs = self.translator.organize_paragraphs(
                        translated_paragraphs, 
                        context=translation_context
                    )
                    if verbose:
                        print(f"  + Organized into {len(translated_paragraphs)} well-structured paragraphs")
                except Exception as e:
                    if verbose:
                        print(f"  ! Paragraph organization failed: {e}, using original paragraphs")
                    # Continue with original paragraphs if organization fails
            
            # Create the PDF with smart layout
            diagram_render_capture = []
            pdf_creation_success = False
            pdf_creation_error = None
            
            try:
                if verbose:
                    print(f"  + Reconstructing PDF page with {len(translated_paragraphs)} paragraphs...")
                
                # Build full page Japanese text for page number extraction
                # Include ALL text boxes (not just cleaned) to get page number
                full_page_japanese = "\n".join([box.get('text', '') for box in text_boxes if box.get('text')])
                
                smart_reconstructor.reconstruct_pdf(
                    text_boxes, 
                    pdf_path, 
                    translated_paragraphs=translated_paragraphs, # Pass pre-translated text
                    translated_diagrams=translated_diagrams,
                    full_page_japanese=full_page_japanese,  # Pass for page number extraction
                    book_context=self.book_context,
                    table_artifacts=tables,
                    chart_artifacts=charts,
                    render_capture=diagram_render_capture
                )
                
                # Verify PDF was actually created
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    pdf_creation_success = True
                    if verbose:
                        print(f"  + PDF reconstruction finished.")
                else:
                    pdf_creation_error = f"PDF file not created or empty: {pdf_path}"
                    if verbose:
                        print(f"  ! PDF verification failed: {pdf_creation_error}")
                        
            except Exception as e:
                pdf_creation_error = str(e)
                if verbose:
                    print(f"  ! PDF creation failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Record PDF creation result
            results['steps']['pdf_creation'] = {
                'success': pdf_creation_success,
                'output_file': f"{self.page_name}_translated.pdf",
                'diagrams_translated': len(translated_diagrams) if translated_diagrams else 0
            }
            if pdf_creation_error:
                results['steps']['pdf_creation']['error'] = pdf_creation_error
            
            # Record artifact summary for visibility (MVP only).
            results['steps']['artifacts'] = {
                'tables': len(tables),
                'charts': len(charts),
                'diagrams': len(diagram_artifacts),
            }
            
            # Provide serializable artifact details for persistence
            try:
                results['steps']['artifact_details'] = {
                    'tables': artifacts_to_dict(tables),
                    'charts': artifacts_to_dict(charts),
                    'diagrams': artifacts_to_dict(diagram_artifacts),
                    'diagram_renderings': diagram_render_capture,
                }
            except Exception as e:
                if verbose:
                    print(f"    ! Artifact serialization error: {e}")
                # Don't fail the whole process for artifact serialization errors
            
            if pdf_creation_success:
                if verbose:
                    print(f"  + Smart layout PDF created: {pdf_path}")
            else:
                # PDF creation failed - this should cause overall failure
                error_msg = pdf_creation_error or "PDF creation failed for unknown reason"
                raise Exception(f"PDF creation failed: {error_msg}")

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
                print(f"Diagrams processed: {len(diagram_regions) if diagram_regions else 0}")
                print(f"Output directory: {self.output_dir}/")
            
            results['success'] = True
            if verbose:
                print(f"  + Page processing complete.")

        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            if verbose:
                import traceback
                print(f"\n[ERROR] An unexpected error occurred in page processing: {str(e)}")
                traceback.print_exc()

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
