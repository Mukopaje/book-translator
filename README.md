# Book Translator - Technical Manual Translation System

A Python-based system for automatically translating Japanese technical manuals to English while preserving diagrams and layouts.

## Project Structure

```
book-translator/
├── src/
│   ├── layout_analysis.py      # Detects text regions and diagrams
│   ├── ocr_extractor.py        # Extracts Japanese text using Tesseract
│   ├── translator.py           # Translates text using OpenAI GPT-4o
│   ├── diagram_processor.py    # Cleans and relabels diagrams
│   ├── pdf_generator.py        # Creates output PDF documents
│   └── main.py                 # Main orchestrator script
├── images_to_process/          # Input image folder
├── output/                     # Output folder for processed files
├── requirements.txt            # Python dependencies
├── .env                        # API keys and configuration
└── README.md                   # This file
```

## Installation

### Prerequisites
- Python 3.10+
- Tesseract OCR (for Japanese text recognition)
- Windows, macOS, or Linux

### Setup Steps

1. **Create and activate virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Python dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Install Tesseract OCR:**
   - **Windows:** Download installer from https://github.com/UB-Mannheim/tesseract/wiki
   - **macOS:** `brew install tesseract`
   - **Linux:** `sudo apt-get install tesseract-ocr tesseract-ocr-jpn`

4. **Configure API keys:**
   Edit `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
   Get your API key from: https://platform.openai.com/api-keys

## Usage

### Quick Start

1. Place your book page images in `images_to_process/` folder
2. Run the main script:
   ```powershell
   python src/main.py --input images_to_process/page_001.jpg
   ```
3. Find translated PDFs in `output/` folder

### Module Usage

Each module can be used independently:

#### Layout Analysis
```python
from src.layout_analysis import LayoutAnalyzer

analyzer = LayoutAnalyzer("path/to/image.jpg")
regions = analyzer.detect_text_regions()
analyzer.visualize_regions("output/visualization.jpg")
```

#### OCR Text Extraction
```python
from src.ocr_extractor import TextExtractor

extractor = TextExtractor()
text = extractor.extract_text("path/to/image.jpg", language='jpn')
```

#### Translation
```python
from src.translator import TextTranslator

translator = TextTranslator()
english_text = translator.translate_text(japanese_text)
```

#### Diagram Processing
```python
from src.diagram_processor import DiagramProcessor

processor = DiagramProcessor("diagram.jpg")
cleaned = processor.clean_diagram()
labels = {"Self": (100, 100), "Off": (200, 100)}
final = processor.relabel_diagram(cleaned, labels)
```

## Workflow

The system processes each page through these steps:

1. **Layout Analysis** - Identifies text blocks vs. diagrams
2. **OCR Extraction** - Extracts Japanese text with Tesseract
3. **Translation** - Sends text to OpenAI GPT-4o for translation
4. **Diagram Cleaning** - Removes original Japanese labels
5. **Diagram Relabeling** - Adds translated English labels
6. **PDF Generation** - Reconstructs pages into output PDF

## Configuration

Edit `.env` to customize:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Tesseract Path (Windows only, if not in PATH)
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# OCR Settings
OCR_LANGUAGE=jpn
OCR_SCALE_PERCENT=200

# Output Settings
OUTPUT_DPI=300
OUTPUT_FORMAT=pdf
```

## Supported Languages

- Japanese (jpn) - Primary
- English (eng) - Output language
- Can be extended to other languages

## API Costs

- **OpenAI API**: ~$0.01 per page (varies by content length)
- **Google Cloud Vision (optional)**: Better OCR accuracy (costs extra)

## Troubleshooting

### "pytesseract.TesseractNotFoundError"
Tesseract is not installed or not in PATH. Install from: https://github.com/UB-Mannheim/tesseract/wiki

### "OpenAI API Error: invalid_api_key"
Check your `.env` file and verify your API key is valid.

### Poor OCR Results
- Try increasing image resolution before processing
- Ensure images are properly scanned (not at an angle)
- Consider using higher quality scans

### Poor Translation Quality
- Provide more context in the translation prompt
- Review and manually correct important sections
- Use consistency glossary for technical terms

## Performance

- **Single page processing time**: ~30-60 seconds (depending on complexity)
- **Bottleneck**: OpenAI API response time
- **Memory usage**: ~100-200 MB per page

## Future Improvements

- [ ] Mobile app for direct scanning
- [ ] Batch processing dashboard
- [ ] Custom translation glossary support
- [ ] Multi-language output
- [ ] Automated quality assurance
- [ ] Web-based interface (Streamlit)
- [ ] Support for PDFs as direct input

## License

MIT License

## Support

For issues and feature requests, please create an issue in the repository.

---

**Built with:** Python, OpenCV, Tesseract, OpenAI GPT-4o, Pillow, ReportLab
