# Book Translator UI Guide - Pagination & Filtering

## Overview of New Interface

### Header Section
```
Pages (200 total)
Showing page 1 of 10 (20 pages per view)
```

Or with active filter:
```
Pages (45 total)
🔍 Filtered by: COMPLETED | Showing page 1 of 3 (20 pages per view)
```

---

## Navigation Controls

### Pagination Bar
```
┌────────────────────────────────────────────────────────────────┐
│ [⏮️ First] [◀️ Prev] Page 3 / 10 [Next ▶️] [Last ⏭️] [Filter ▼] │
└────────────────────────────────────────────────────────────────┘
```

**Buttons**:
- **⏮️ First**: Jump to first page (page 1)
- **◀️ Prev**: Go back 20 pages
- **Next ▶️**: Advance 20 pages
- **⏭️ Last**: Jump to last page
- **Filter dropdown**: Choose status to filter by

---

## Status Filter Options

### All Statuses Available:
1. **All** - Show all pages (no filter)
2. **UPLOADED** - Uploaded but not queued yet
3. **QUEUED** - In queue, waiting to be processed
4. **PROCESSING** - Currently being processed by worker
5. **COMPLETED** - Successfully processed, quality ≥ 70
6. **FAILED** - Processing failed, has error message
7. **NEEDS_REVIEW** - Completed but quality < 70

### How Filters Work:
```
Select "COMPLETED" filter
↓
API call: GET /pages?status_filter=COMPLETED
↓
Shows only completed pages
↓
Page count updates to show filtered total
```

---

## Batch Action Bar

```
┌────────────────────────────────────────────────────────────────────────┐
│ [☑️ Select Page (20)] [🚀 Queue All] [🔄 Refresh] [🔁 Reprocess (5)] │
└────────────────────────────────────────────────────────────────────────┘
```

**Buttons**:
- **☑️ Select Page (20)**: Select all visible pages on current view
- **🚀 Queue All (Async)**: Queue all eligible pages across ALL pages (not just visible)
- **🔄 Refresh Status**: Reload current page from backend
- **🔁 Reprocess Selected (N)**: Reprocess N selected pages

---

## Page Card Layout

Each page shows as an expandable card:

```
┌─────────────────────────────────────────────────────────────────┐
│ [✓] [Thumbnail] ▶ 47. page_047.jpg - COMPLETED                 │
├─────────────────────────────────────────────────────────────────┤
│ Expanded view:                                                   │
│                                                                  │
│ [Image Preview]    │ Page #: 47                                 │
│ (200px)            │ Status: COMPLETED                          │
│                    │ Quality: ✅ Excellent (95/100)             │
│                    │ 📝 OCR: 1,234 chars                        │
│                    │ 🌐 Translation: 1,156 chars                │
│                    │                                             │
│                    │ [View PDF] [📥 Download PDF]               │
└─────────────────────────────────────────────────────────────────┘
```

### Quality Score Display

Quality scores are color-coded:

- 🟢 **Excellent (90-100)** - Green
- 🔵 **Good/Acceptable (70-89)** - Blue
- 🟠 **Poor (50-69)** - Orange
- 🔴 **Failed (0-49)** - Red

### Page with Quality Issues

```
┌─────────────────────────────────────────────────────────────────┐
│ [✓] [Thumbnail] ▶ 52. page_052.jpg - NEEDS_REVIEW              │
├─────────────────────────────────────────────────────────────────┤
│ [Image Preview]    │ Page #: 52                                 │
│                    │ Status: NEEDS_REVIEW                       │
│                    │ Quality: ⚠️ Poor (55/100)                  │
│                    │                                             │
│                    │ ▼ ⚠️ 3 Quality Issues                      │
│                    │   • [warning] Diagram has only 1 label     │
│                    │   • [error] Table has 40% empty cells      │
│                    │   • [warning] Translation short (0.4x)     │
│                    │                                             │
│                    │ [🔄 Replace Image]                         │
│                    │ [🚀 Queue]                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Common Workflows

### Workflow 1: Review Completed Pages

1. Select filter: **COMPLETED**
2. Navigate through pages using pagination
3. Check quality scores
4. Download PDFs for high-quality pages

### Workflow 2: Fix Low-Quality Pages

1. Select filter: **NEEDS_REVIEW**
2. Review quality issues for each page
3. For image quality issues:
   - Click "🔄 Replace Image"
   - Upload better quality scan
   - Page resets to UPLOADED
4. Click "🚀 Queue" to reprocess

### Workflow 3: Monitor Processing

1. Select filter: **PROCESSING** or **QUEUED**
2. Interface auto-refreshes every 5 seconds
3. Watch status change to COMPLETED or NEEDS_REVIEW
4. Switch filter to review results

### Workflow 4: Batch Reprocessing

1. Navigate to pages needing reprocessing
2. Check boxes for pages to reprocess
3. Click "🔁 Reprocess Selected (N)"
4. Pages are queued for processing

---

## Empty States

### No Pages Uploaded
```
┌──────────────────────────────┐
│ ℹ️ Upload pages to begin.    │
└──────────────────────────────┘
```

### No Pages Match Filter
```
┌────────────────────────────────────────────────────────────┐
│ ℹ️ No pages found with status 'COMPLETED'.                 │
│    Try changing the filter or upload pages to begin.       │
└────────────────────────────────────────────────────────────┘
```

### Processing in Progress
```
┌────────────────────────────────────────────────────────────┐
│ ⏳ 15 page(s) in progress.                                  │
│    Auto-refreshing every 5 seconds...                      │
└────────────────────────────────────────────────────────────┘
```

---

## Sidebar Information

The sidebar always shows the complete project status:

```
┌─────────────────────────┐
│ Current Project         │
│                         │
│ Title: Technical Manual │
│ Author: ABC Corp        │
│ Progress: 100/200 pages │
│                         │
│ [📚 Download Book]      │
└─────────────────────────┘
```

This count (100/200) is the **total** across all statuses, not affected by filters.

---

## Keyboard Navigation (Future)

Planned keyboard shortcuts:
- `Ctrl+→` : Next page
- `Ctrl+←` : Previous page
- `Ctrl+Home` : First page
- `Ctrl+End` : Last page
- `Ctrl+R` : Refresh
- `/` : Focus filter dropdown

---

## Tips for Large Books (500+ Pages)

### Best Practices:

1. **Use Filters Strategically**
   - Start with "UPLOADED" to queue new pages
   - Switch to "PROCESSING" to monitor
   - Use "NEEDS_REVIEW" to find issues
   - Filter by "COMPLETED" to download results

2. **Pagination Navigation**
   - Use "Last ⏭️" to check most recent uploads
   - Use "First ⏮️" to start from beginning
   - Page indicator helps track position

3. **Batch Operations**
   - "Queue All" processes across all pages, not just visible
   - Select pages on current view for targeted reprocessing
   - Refresh periodically to see updated statuses

4. **Quality Management**
   - Filter by NEEDS_REVIEW regularly during bulk processing
   - Address quality issues early to avoid rework
   - Replace poor images immediately, don't accumulate them

---

## Performance Expectations

| Operation | Time | Pages Loaded |
|-----------|------|--------------|
| Load project | < 1s | 20 pages |
| Navigate to next page | < 0.5s | 20 pages |
| Apply filter | < 1s | 20 filtered pages |
| Refresh status | < 1s | Current 20 pages |
| Switch projects | < 1s | First 20 of new project |

---

## Troubleshooting UI Issues

### Pages not showing after selecting project
1. Check if filter is active (shows "🔍 Filtered by:")
2. Try changing filter to "All"
3. Click "🔄 Refresh Status"
4. Check browser console for errors

### Pagination stuck or disabled
1. Check page count: "Pages (X total)"
2. If X = 0, no pages match filter
3. Clear filter and try again
4. Verify project has pages in sidebar

### Quality scores not visible
1. Only shows for processed pages
2. Run database migration if scores are missing
3. Reprocess pages to generate scores

---

## Summary of Visual Indicators

### Status Emojis:
- 📤 UPLOADED
- ⏰ QUEUED
- ⚙️ PROCESSING
- ✅ COMPLETED
- ❌ FAILED
- ⚠️ NEEDS_REVIEW

### Quality Indicators:
- 🟢 Excellent (90-100)
- 🔵 Good (70-89)
- 🟠 Poor (50-69)
- 🔴 Failed (0-49)

### Action Buttons:
- 🚀 Queue for processing
- 🔄 Replace image
- 📥 Download PDF
- 👁️ View PDF
- ❌ Remove page

The interface is designed to make managing large book translation projects efficient and intuitive!
