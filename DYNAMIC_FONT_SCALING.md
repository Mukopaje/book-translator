# Dynamic Font Scaling Implementation

## Problem
Japanese text translates to English with 30-50% expansion in character count. This causes:
- Content overflow on pages
- Text that fit on one Japanese page doesn't fit on one English page
- Technical terms expand even more (噴射装置 → "fuel injection system")

## Solution: Hybrid Approach (Option 4)

Implemented dynamic font and line height scaling based on actual text expansion ratio.

## How It Works

### 1. Text Expansion Calculation
```python
def _calculate_text_expansion(self, text_boxes, full_page_japanese):
    # Count Japanese characters (without spaces)
    japanese_char_count = len(re.sub(r'\s+', '', full_page_japanese))
    
    # Count English characters (without spaces)
    english_char_count = sum(len(re.sub(r'\s+', '', box['translation'])) 
                             for box in text_boxes if box.get('translation'))
    
    # Calculate expansion ratio
    expansion_ratio = english_char_count / japanese_char_count
```

### 2. Dynamic Scaling Rules

**No Scaling (expansion < 1.3x)**
- Font size: 10pt
- Line height: 1.4x font size
- No adjustments needed

**Light Scaling (expansion 1.3x - 1.5x)**
- Font size: 9.5pt - 8.5pt (5-15% reduction)
- Line height: 1.26x font size (10% tighter)
- Example: 1.4x expansion → 9pt font

**Heavy Scaling (expansion > 1.5x)**
- Font size: 8pt minimum (20% reduction max)
- Line height: 1.26x font size
- Prevents text from becoming too small to read

### 3. Formula
```
scale_factor = max(0.80, 1.0 - (expansion_ratio - 1.0) * 0.25)
font_size = 10pt * scale_factor
line_height_multiplier = 1.26 if scale_factor < 0.95 else 1.4
line_height = font_size * line_height_multiplier
```

## Examples

**Example 1: Moderate Expansion**
- Japanese: 500 characters
- English: 700 characters
- Expansion: 1.4x
- Result: Font 9pt, Line height 11.34pt (1.26x)
- **Saves ~15% vertical space**

**Example 2: Heavy Expansion**
- Japanese: 500 characters
- English: 1000 characters  
- Expansion: 2.0x
- Result: Font 8pt (minimum), Line height 10.08pt
- **Saves ~20% vertical space**

**Example 3: Minimal Expansion**
- Japanese: 500 characters
- English: 600 characters
- Expansion: 1.2x
- Result: Font 10pt (no change), Line height 14pt
- **No scaling needed**

## Benefits

1. **Automatic**: No manual intervention needed per page
2. **Proportional**: Scales based on actual expansion, not fixed
3. **Readable**: Never goes below 8pt font size
4. **Conservative**: Only applies when expansion ≥ 1.3x
5. **Safe**: Falls back to 1.0 scale on any error

## Files Modified

- `src/smart_layout_reconstructor.py`:
  - Added `_calculate_text_expansion()` method
  - Dynamic `font_size` and `line_height` calculation
  - Updated internal functions to use local variables

## Testing

To test with a specific page:
```bash
# Process a page and check console output
# Look for lines like:
# [PDF Scaling] Japanese: 850 chars, English: 1200 chars
# [PDF Scaling] Expansion ratio: 1.41x
# [PDF Scaling] Applying scale factor: 0.90
```

## Future Enhancements

If pages still overflow after scaling:
- **Page Splitting**: Automatically create Page 387a, 387b when needed
- **Column Compression**: Reduce margins for multi-column layouts
- **Smart Pagination**: Detect natural break points for splits
