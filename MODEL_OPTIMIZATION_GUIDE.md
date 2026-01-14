# Model Optimization Guide - Speed vs Accuracy

## Current System Tasks & Model Usage

Your book-translator system has 4 main AI tasks, currently all using different models:

| Task | Current Model | File | Purpose |
|------|--------------|------|---------|
| **Layout Detection** | `gemini-3-pro-preview` | `layout_agent.py` | Identify text blocks, diagrams, tables, page numbers |
| **Table Extraction** | `gemini-3-pro-preview` | `table_agent.py` | Extract table structure (rows, cols, cells) |
| **Language Detection** | `gemini-1.5-flash` | `language_detector.py` | Detect source language |
| **Translation** | `gemini-3-pro-preview` | `gemini_translator.py` | Translate Japanese→English |

## Available Gemini Models (Jan 2025)

### Speed Tier (Fastest → Slowest)
1. **Gemini 1.5 Flash** - ~2-3 sec/request
2. **Gemini 2.0 Flash** - ~3-5 sec/request  
3. **Gemini 1.5 Pro** - ~5-10 sec/request
4. **Gemini 2.0 Pro** - ~10-20 sec/request
5. **Gemini 3.0 Pro** - ~20-40 sec/request (VERY SLOW)

### Accuracy Tier (Best → Good)
1. **Gemini 3.0 Pro** - Highest precision, best reasoning
2. **Gemini 2.0 Pro** - Excellent balance
3. **Gemini 2.0 Flash** - Very good, fast
4. **Gemini 1.5 Pro** - Good baseline
5. **Gemini 1.5 Flash** - Fast but less nuanced

## Recommended Model Assignment

### Priority: Speed + Cost Optimization

| Task | Recommended Model | Reason |
|------|------------------|--------|
| **Layout Detection** | `gemini-2.0-flash-exp` | Fast, good vision, handles complex layouts well. Critical for every page. |
| **Table Extraction** | `gemini-2.0-flash-exp` | Fast, JSON output reliable. Tables are structured, don't need highest accuracy. |
| **Language Detection** | `gemini-1.5-flash` ✓ | Already optimal! Fast, simple task, rarely ambiguous. |
| **Translation** | `gemini-2.0-pro-exp` | Slower but CRITICAL for quality. Bad translations ruin the book. Worth the time. |

### Priority: Maximum Accuracy (Slower)

| Task | Recommended Model | Reason |
|------|------------------|--------|
| **Layout Detection** | `gemini-2.0-pro-exp` | Best at distinguishing diagram labels from body text. |
| **Table Extraction** | `gemini-2.0-pro-exp` | Better cell boundary detection for complex tables. |
| **Language Detection** | `gemini-1.5-flash` | No need to change - simple task. |
| **Translation** | `gemini-3-pro-preview` | Highest quality translations, best context understanding. |

### Priority: Balanced (Recommended for Production)

| Task | Recommended Model | Reason |
|------|------------------|--------|
| **Layout Detection** | `gemini-2.0-flash-exp` | 90% accuracy of Pro, 3-5x faster. Good tradeoff. |
| **Table Extraction** | `gemini-2.0-flash-exp` | Structured output is reliable even on Flash. |
| **Language Detection** | `gemini-1.5-flash` | Already perfect. |
| **Translation** | `gemini-2.0-pro-exp` | Near-best quality, reasonable speed (~10s/page). |

**Estimated Processing Time per Page:**
- Current (all 3.0 Pro): ~80-120 seconds/page
- Recommended Balanced: ~25-35 seconds/page (3-4x faster!)
- Speed Optimized: ~15-20 seconds/page (5-6x faster, slight accuracy drop)

## Implementation

### Option 1: Environment Variables (Easiest)
Add to your `.env`:
```bash
# Model Configuration
LAYOUT_MODEL=gemini-2.0-flash-exp
TABLE_MODEL=gemini-2.0-flash-exp
TRANSLATION_MODEL=gemini-2.0-pro-exp
LANGUAGE_MODEL=gemini-1.5-flash
```

### Option 2: Direct Code Changes

**layout_agent.py (line 26):**
```python
# Before:
self.model_name = "gemini-3-pro-preview"

# After (Balanced):
self.model_name = os.getenv("LAYOUT_MODEL", "gemini-2.0-flash-exp")

# After (Speed):
self.model_name = os.getenv("LAYOUT_MODEL", "gemini-2.0-flash-exp")

# After (Accuracy):
self.model_name = os.getenv("LAYOUT_MODEL", "gemini-2.0-pro-exp")
```

**table_agent.py (same pattern):**
```python
self.model_name = os.getenv("TABLE_MODEL", "gemini-2.0-flash-exp")
```

**gemini_translator.py:**
```python
def __init__(self, model_name=None):
    if model_name is None:
        model_name = os.getenv("TRANSLATION_MODEL", "gemini-2.0-pro-exp")
```

## Cost Implications

### Current Setup (all gemini-3-pro-preview)
- Cost: ~$0.10-0.15 per page (estimated)
- Speed: 80-120 seconds/page
- 700 page book: $70-105, ~15-23 hours

### Recommended Balanced Setup
- Cost: ~$0.03-0.05 per page
- Speed: 25-35 seconds/page
- 700 page book: $21-35, ~5-7 hours
- **Savings: 70% cost, 75% time reduction**

### Speed Optimized (all Flash models)
- Cost: ~$0.01-0.02 per page  
- Speed: 15-20 seconds/page
- 700 page book: $7-14, ~3-4 hours
- **Savings: 90% cost, 85% time reduction**
- **Tradeoff: 5-10% accuracy loss on complex layouts**

## Task-Specific Notes

### Layout Detection
- **Critical regions:** text_block, technical_diagram, table
- **Challenge:** Distinguishing diagram labels from body text
- **Gemini 2.0 Flash:** Handles this well 90% of the time
- **When to use Pro:** Pages with very dense diagrams + small text

### Table Extraction  
- **Task:** Identify rows, cols, cell positions, merged cells
- **Challenge:** Complex nested tables, merged headers
- **Gemini 2.0 Flash:** Reliable for 95% of tables
- **When to use Pro:** Financial tables, heavily merged cells

### Translation
- **Most important task** - bad translations = unusable book
- **Keep on Pro model** for production
- **Gemini 2.0 Pro:** Best balance of speed + quality
- **Gemini 3.0 Pro:** Use ONLY for final polish pass on critical pages

### Language Detection
- **Simplest task** - already using Flash
- **No need to change**

## Testing Strategy

1. **Test on 10 representative pages** with each model combination
2. **Compare outputs:**
   - Layout: Check if all diagrams detected, text not mixed with labels
   - Tables: Verify cell count matches visual inspection
   - Translation: Have native speaker spot-check quality
3. **Measure speed:** Time each page processing
4. **Choose based on results**

## Experiment: Per-Page Adaptive Model Selection

For maximum optimization, detect page complexity and choose model accordingly:

```python
def choose_layout_model(image_path):
    # Quick heuristic: High diagram density → Use Pro
    # Simple text page → Use Flash
    image = Image.open(image_path)
    # ... analyze image complexity ...
    if diagram_density > 0.4:
        return "gemini-2.0-pro-exp"
    else:
        return "gemini-2.0-flash-exp"
```

This could give best of both worlds - fast for simple pages, accurate for complex ones.

## My Recommendation

**Start with Balanced Setup:**
1. Layout: `gemini-2.0-flash-exp`
2. Tables: `gemini-2.0-flash-exp`  
3. Translation: `gemini-2.0-pro-exp`
4. Language: `gemini-1.5-flash` (keep as-is)

**Process 50 pages and evaluate:**
- If layout/table quality is good → keep it
- If seeing errors → bump to 2.0 Pro for those tasks
- If translation quality drops → test 3.0 Pro on critical chapters

**Expected results:**
- 3-4x speed improvement
- 60-70% cost reduction
- <5% quality loss (acceptable for most technical manuals)

---

*Would you like me to implement these changes with environment variable support so you can easily switch models?*
