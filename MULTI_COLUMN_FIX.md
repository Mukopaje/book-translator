# Multi-Column Layout Issue Analysis

## Problem
Page 387 has a 2-column layout with:
- Left column: Diagram (a, b, c, d)
- Right column: Legend table with numbered items

Current output:
1. Table renders correctly
2. Diagram renders
3. **Duplicate**: Same content renders again as plain text list
4. **Duplicate**: Diagram C renders again
5. Total: 5 pages instead of 1

## Root Cause
The AI correctly detects the 2-column layout and assigns reading orders, but our PDF renderer:
1. Processes sections in reading order (correct)
2. But doesn't handle "side-by-side" positioning - it stacks everything vertically
3. Text boxes from table regions might be getting re-rendered as paragraphs

## Solution Options

### Option 1: Simple - Stack vertically in reading order (RECOMMENDED)
- Accept that multi-column layouts will become single-column in output
- Ensure no duplicates by not rendering text boxes that belong to table/diagram regions
- Fast to implement, works for all cases

### Option 2: Complex - True side-by-side rendering
- Use ReportLab Frames or manual X-positioning
- Calculate column widths based on layout_columns
- Render sections side-by-side when they have same Y-range but different columns
- Complex, fragile, may not work well with varying content heights

## Recommendation
Go with Option 1 for now - ensure clean vertical flow without duplicates.
Later, we can add true multi-column support if needed.
