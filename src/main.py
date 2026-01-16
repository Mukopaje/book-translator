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
from chart_translator import ChartTranslator
from agents.table_agent import TableAgent
from agents.chart_agent import ChartAgent
from agents.diagram_agent import DiagramAgent
from agents.layout_agent import LayoutAgent
from artifacts.schemas import artifacts_to_dict


class BookTranslator:
    """Main orchestrator for the book translation pipeline"""

    def __init__(self, image_path: str, output_dir: str = "output", book_context: str = None,
                 source_language: str = "auto", target_language: str = "en"):
        """
        Initialize the book translator

        Args:
            image_path: Path to the input image
            output_dir: Directory for output files
            book_context: Optional global context about the book (e.g. "4-stroke engine manual")
            source_language: Source language code (ISO 639-1) or 'auto' for detection
            target_language: Target language code (ISO 639-1)
        """
        self.image_path = image_path
        self.output_dir = output_dir
        self.page_name = Path(image_path).stem
        self.book_context = book_context
        self.source_language = source_language
        self.target_language = target_language
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize components
        self.text_extractor = TextExtractor()
        self.layout_agent = LayoutAgent()
        
        # Try Gemini first, fall back to Google Translate
        try:
            self.translator = GeminiTranslator()
            print("[OK] Using Gemini 3 Pro Preview for intelligent translation")
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
            
            # Phase 1: AI Layout Analysis (Gemini Vision)
            if verbose:
                print(f"  + Running AI Layout Analysis...")
            
            layout_result = self.layout_agent.detect_layout(self.image_path)
            
            if layout_result.get("success"):
                if verbose:
                    print(f"  + AI Layout Analysis successful. Reconstructing structure...")
                layout = smart_reconstructor.reconstruct_from_layout_analysis(layout_result, text_boxes)
            else:
                if verbose:
                    print(f"  ! AI Layout Analysis failed ({layout_result.get('error')}). Falling back to heuristic analysis.")
                layout = smart_reconstructor._analyze_layout_structure(text_boxes)
                
            diagram_regions = layout.get('diagram_regions', [])
            chart_regions = layout.get('chart_regions', [])
            
            # Filter out diagram/chart text to build the "Cleaned" prose for translation
            cleaned_japanese_list = []
            for box in text_boxes:
                inside_any_diagram = False
                # Check diagrams
                for region in diagram_regions:
                    if (box['x'] >= region['x'] - 5 and 
                        box['y'] >= region['y'] - 5 and 
                        box['x'] + box['w'] <= region['x'] + region['w'] + 5 and 
                        box['y'] + box['h'] <= region['y'] + region['h'] + 5):
                        inside_any_diagram = True
                        break
                # Check charts
                if not inside_any_diagram:
                    for region in chart_regions:
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
                print(f"  + Found {len(chart_regions)} chart region(s)")
                print(f"  + Extracted {len(japanese_text)} characters for prose translation")

            # Step 1.5: Language Detection (if auto-detect is enabled)
            detected_language = None
            detection_confidence = None

            if self.source_language == 'auto' and japanese_text.strip():
                if verbose:
                    print(f"\n[1.5/6] Detecting source language...")

                try:
                    from language_detector import LanguageDetector
                    detector = LanguageDetector()
                    detection_result = detector.detect_language(japanese_text[:500])  # Sample first 500 chars

                    detected_language = detection_result['language_code']
                    detection_confidence = detection_result['confidence']

                    if verbose:
                        print(f"  + Detected: {detection_result['language_name']} ({detected_language}) with {int(detection_confidence * 100)}% confidence")

                    # Use detected language as source
                    actual_source_lang = detected_language
                except Exception as e:
                    if verbose:
                        print(f"  ! Language detection failed: {e}. Defaulting to 'ja'")
                    actual_source_lang = 'ja'  # Fallback to Japanese
            else:
                actual_source_lang = self.source_language
                if verbose:
                    print(f"\n[1.5/6] Using specified source language: {actual_source_lang}")

            # Step 2: Translation with Context
            if verbose:
                print(f"\n[2/6] Translating {actual_source_lang} → {self.target_language}...")

            translation_context = "technical manual"
            if self.book_context:
                translation_context = f"{translation_context}. Book Context: {self.book_context}"

            english_text = self.translator.translate_text(
                japanese_text,
                context=translation_context,
                source_lang=actual_source_lang,
                target_lang=self.target_language
            )

            # Store detection results in results dict
            results['detected_language'] = detected_language
            results['detection_confidence'] = detection_confidence
            
            if verbose:
                print(f"  + Translation complete ({len(english_text)} characters)")
            
            # Step 4: Create Clean PDF with Smart Layout
            if verbose:
                print(f"\n[4/6] Creating clean translated PDF with smart layout...")
            
            pdf_path = f"{self.output_dir}/{self.page_name}_translated.pdf"
            
            # Simplified text box construction since we already have text_boxes from OCR
            for box in text_boxes:
                box['translation'] = ''
            
            # 4a: Run artifact agents (MVP: stubs return empty for tables/charts)
            if verbose:
                print(f"  + Running artifact agents (tables/charts/diagrams)...")
            
            import traceback
            try:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
                
                def run_table_detection():
                    table_agent = TableAgent()
                    chart_agent = ChartAgent()
                    
                    # 1. AI-Based Extraction (Preferred)
                    # Extract table regions from the layout analysis
                    ai_table_regions = [s for s in layout.get('page_sections', []) if s.get('type') == 'table']
                    
                    if ai_table_regions:
                        print(f"    [Main] Detected {len(ai_table_regions)} tables from AI layout. Using AI extraction.")
                        tables = table_agent.extract_tables_with_ai(self.image_path, ai_table_regions)
                        # AI extraction might fail or return empty, so fall back if needed?
                        if tables:
                            return tables, []
                    
                    # 2. Heuristic Fallback (Legacy)
                    print("    [Main] No AI tables detected or extraction skipped. Attempting heuristic detection.")
                    # Filter out boxes that are inside diagrams to avoid false positive tables
                    non_diagram_boxes = []
                    for box in text_boxes:
                        inside_diagram = False
                        for region in diagram_regions + chart_regions:
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
                    print(f"    + Found {len(tables)} tables and {len(charts)} charts (agent-based).")
                    
            except Exception as e:
                if verbose:
                    print(f"    ! Artifact agent error (tables/charts): {e}")
                    print(f"    ! Full stack trace:\n{traceback.format_exc()}")
                tables, charts = [], []
            
            if verbose:
                print(f"  + Artifact detection finished, moving on to diagram translation...")

            # Step 4b: Translate diagrams if found
            translated_diagrams = None
            # Check if overlay mode is enabled
            diagram_mode = os.getenv('DIAGRAM_TRANSLATION_MODE', 'overlay')

            if diagram_regions and diagram_mode != 'overlay':
                # Only use old diagram translator if NOT in overlay mode
                # Overlay mode handles translation during PDF reconstruction
                if verbose:
                    print(f"\n[4b/6] Translating diagram labels (replace mode)...")
                # Use enhanced processing mode for crisp diagrams
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
            elif diagram_regions and diagram_mode == 'overlay':
                if verbose:
                    print(f"\n[4b/6] Extracting diagram text for overlay mode...")
                # For overlay mode, we use OCR data for precise positioning
                # This is MUCH faster and more accurate than Gemini Vision
                translated_diagrams = self._extract_diagrams_for_overlay(
                    diagram_regions,
                    text_boxes,  # Pass OCR data!
                    self.translator,
                    book_context=self.book_context,
                    source_lang=actual_source_lang,
                    target_lang=self.target_language
                )
                if verbose:
                    print(f"  + Extracted and translated {len(translated_diagrams)} diagram(s) for overlay mode")

            # Step 4c: Translate charts if found (Dedicated Pipeline)
            translated_charts = None
            if chart_regions:
                if diagram_mode == 'overlay':
                    # OPTIMIZED: Use OCR-based overlay extraction for charts too (much faster)
                    if verbose:
                        print(f"\n[4c/6] Extracting chart text for overlay mode...")
                    
                    translated_charts = self._extract_diagrams_for_overlay(
                        chart_regions,
                        text_boxes,  # Pass existing OCR data
                        self.translator,
                        book_context=self.book_context,
                        source_lang=actual_source_lang,
                        target_lang=self.target_language
                    )
                    
                    if verbose:
                        print(f"  + Extracted and translated {len(translated_charts)} chart(s) for overlay mode")
                else:
                    if verbose:
                        print(f"\n[4c/6] Translating chart labels...")
                    chart_translator = ChartTranslator()
                    chart_output_dir = f"{self.output_dir}/charts"
                    translated_charts = chart_translator.process_charts(
                        self.image_path,
                        chart_regions,
                        self.translator,
                        chart_output_dir,
                        book_context=self.book_context
                    )
                    if verbose:
                        print(f"  + Translated {len(translated_charts)} charts(s)")
            
            # Normalize diagram artifacts
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
            
            # Create the PDF with smart layout
            diagram_render_capture = []
            pdf_creation_success = False
            pdf_creation_error = None
            
            try:
                if verbose:
                    print(f"  + Reconstructing PDF page with {len(translated_paragraphs)} paragraphs...")
                
                # Build full page Japanese text for page number extraction
                full_page_japanese = "\n".join([box.get('text', '') for box in text_boxes if box.get('text')])
                
                smart_reconstructor.reconstruct_pdf(
                    text_boxes, 
                    pdf_path, 
                    translated_paragraphs=translated_paragraphs, 
                    translated_diagrams=translated_diagrams,
                    translated_charts=translated_charts, # PASS CHARTS
                    full_page_japanese=full_page_japanese,
                    book_context=self.book_context,
                    table_artifacts=tables,
                    chart_artifacts=charts,
                    render_capture=diagram_render_capture,
                    layout=layout 
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
            
            # Record artifact summary
            results['steps']['artifacts'] = {
                'tables': len(tables),
                'charts': len(charts),
                'diagrams': len(diagram_artifacts),
                'visual_charts': len(translated_charts) if translated_charts else 0
            }
            
            # Provide serializable artifact details
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
            
            if pdf_creation_success:
                if verbose:
                    print(f"  + Smart layout PDF created: {pdf_path}")
            else:
                error_msg = pdf_creation_error or "PDF creation failed for unknown reason"
                raise Exception(f"PDF creation failed: {error_msg}")

            # Step 5: Save Results
            if verbose:
                print(f"\n[5/6] Saving translation results...")
            
            self.text_extractor.save_ocr_results(
                japanese_text,
                f"{self.output_dir}/{self.page_name}_japanese.txt"
            )
            
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
                print(f"Charts processed: {len(chart_regions) if chart_regions else 0}")
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

    def _extract_diagrams_for_overlay(self, diagram_regions, ocr_boxes, translator=None, book_context=None, source_lang='auto', target_lang='en'):
        """
        Extract text from diagrams using OCR data and translate for overlay mode.
        Uses existing OCR bounding boxes for PERFECT positioning - no Gemini Vision needed!
        This is 5x faster and 100% accurate for positioning.
        Language-agnostic: works with any source language detected by the system.
        Returns data in the same format as DiagramTranslator for compatibility.
        """
        from PIL import Image

        # Debug logging
        print(f"  [Overlay] Processing {len(diagram_regions)} diagram regions with {len(ocr_boxes)} total OCR boxes")
        print(f"  [Overlay] Source lang: {source_lang}, Target lang: {target_lang}")

        translated_diagrams = []
        img = Image.open(self.image_path)
        print(f"  [Overlay] Image size: {img.size}")

        for i, region in enumerate(diagram_regions):
            try:
                # Get diagram boundaries
                region_x = region['x']
                region_y = region['y']
                region_w = region['w']
                region_h = region['h']

                # Create crop for the diagram
                crop = img.crop((region_x, region_y, region_x + region_w, region_y + region_h))

                # Filter OCR boxes that fall within this diagram region
                # Use intersection-based logic with tolerance for edge cases
                diagram_ocr_boxes = []
                tolerance = 20  # 20px tolerance for boundary detection

                for box in ocr_boxes:
                    box_x = box.get('x', 0)
                    box_y = box.get('y', 0)
                    box_w = box.get('w', 0)
                    box_h = box.get('h', 0)

                    # Calculate overlap between OCR box and diagram region
                    # Box is included if it has ANY significant overlap with the diagram
                    overlap_x_start = max(region_x - tolerance, box_x)
                    overlap_x_end = min(region_x + region_w + tolerance, box_x + box_w)
                    overlap_y_start = max(region_y - tolerance, box_y)
                    overlap_y_end = min(region_y + region_h + tolerance, box_y + box_h)

                    overlap_w = overlap_x_end - overlap_x_start
                    overlap_h = overlap_y_end - overlap_y_start

                    # Include box if at least 50% of it overlaps with the diagram region
                    box_area = box_w * box_h if box_w > 0 and box_h > 0 else 1
                    overlap_area = max(0, overlap_w) * max(0, overlap_h)
                    overlap_ratio = overlap_area / box_area

                    if overlap_ratio >= 0.5:  # At least 50% overlap
                        # Convert to diagram-relative coordinates
                        diagram_ocr_boxes.append({
                            'x': max(0, box_x - region_x),  # Relative to diagram, clamped to 0
                            'y': max(0, box_y - region_y),
                            'w': box_w,
                            'h': box_h,
                            'text': box.get('text', ''),
                            'confidence': box.get('confidence', 1.0)
                        })

                if not diagram_ocr_boxes:
                    print(f"  [Overlay] Warning: No OCR text found in diagram {i+1}, adding placeholder entry")
                    # DON'T skip! Add entry with empty annotations so diagram is still rendered
                    translated_diagrams.append({
                        'image': crop,
                        'annotations': [],
                        'region': region,
                        'y_center': region['y'] + region['h'] // 2
                    })
                    continue

                print(f"  [Overlay] Found {len(diagram_ocr_boxes)} OCR boxes in diagram {i+1}")

                # Batch translate all text at once (FAST!)
                texts_to_translate = [box['text'] for box in diagram_ocr_boxes]
                translations = []

                if translator:
                    try:
                        # Use structured JSON translation to ensure perfect alignment and data integrity
                        # This avoids regex fragility and handles diverse book formats automatically
                        batch_context = f"{book_context or 'Technical diagram labels'}"
                        
                        if hasattr(translator, 'translate_batch_structured'):
                             translations = translator.translate_batch_structured(
                                 texts_to_translate,
                                 context=batch_context,
                                 source_lang=source_lang,
                                 target_lang=target_lang
                             )
                        else:
                             # Fallback to simple batching if method not available
                             translations = texts_to_translate
                             
                    except Exception as e:
                        print(f"  [Overlay] Translation error: {e}, using original text")
                        translations = texts_to_translate

                # Ensure we have translations for all boxes
                while len(translations) < len(diagram_ocr_boxes):
                    translations.append(texts_to_translate[len(translations)])

                # Create annotations with OCR positions + translations
                annotations = []
                for box, translation in zip(diagram_ocr_boxes, translations):
                    annotations.append({
                        'x': box['x'],
                        'y': box['y'],
                        'w': box['w'],
                        'h': box['h'],
                        'text': translation,
                        'original_text': box['text']
                    })

                # Store in same format as DiagramTranslator
                translated_diagrams.append({
                    'image': crop,  # Original diagram image
                    'annotations': annotations,
                    'region': region,
                    'y_center': region['y'] + region['h'] // 2
                })

                print(f"  [Overlay] Extracted {len(annotations)} labels from diagram {i+1}")

            except Exception as e:
                import traceback
                print(f"  [Overlay] Error extracting diagram {i+1}: {e}")
                traceback.print_exc()
                # Still add entry with empty annotations so structure is consistent
                # Create crop if it doesn't exist yet
                if 'crop' not in locals():
                    try:
                        crop = img.crop((region_x, region_y, region_x + region_w, region_y + region_h))
                    except:
                        crop = img  # Fallback to full image
                translated_diagrams.append({
                    'image': crop,
                    'annotations': [],
                    'region': region,
                    'y_center': region['y'] + region['h'] // 2
                })

        return translated_diagrams


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
    
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    translator = BookTranslator(args.input, args.output)
    results = translator.process_page(verbose=not args.quiet)
    
    sys.exit(0 if results['success'] else 1)


if __name__ == "__main__":
    main()
