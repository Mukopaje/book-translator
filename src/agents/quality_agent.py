"""
Quality Verification Agent
Automatically verifies translation quality by analyzing input/output artifacts
"""

import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from PIL import Image

logger = logging.getLogger(__name__)


class QualityVerificationAgent:
    """
    Verifies translation quality by comparing input/output and checking for:
    - Diagrams: Label coverage, text clarity, annotation completeness
    - Charts: Data completeness, axis labels, legend presence
    - Tables: Row count, cell completeness, empty cell ratio
    - Text: Translation completeness, paragraph count, character ratio
    """

    def __init__(self,
                 min_diagram_labels: int = 2,
                 max_empty_table_cells_ratio: float = 0.3,
                 min_translation_ratio: float = 0.5,
                 max_translation_ratio: float = 2.5):
        """
        Initialize quality verification agent with thresholds.

        Args:
            min_diagram_labels: Minimum number of labels expected in diagrams
            max_empty_table_cells_ratio: Maximum ratio of empty cells in tables (0.3 = 30%)
            min_translation_ratio: Minimum ratio of translated/original text length
            max_translation_ratio: Maximum ratio of translated/original text length
        """
        self.min_diagram_labels = min_diagram_labels
        self.max_empty_table_cells_ratio = max_empty_table_cells_ratio
        self.min_translation_ratio = min_translation_ratio
        self.max_translation_ratio = max_translation_ratio

        # Severity weights for scoring
        self.severity_weights = {
            'critical': 25,  # -25 points per critical issue
            'error': 15,     # -15 points per error
            'warning': 5,    # -5 points per warning
            'info': 0        # No penalty for info
        }

    def verify_page_quality(self,
                           input_image_path: str,
                           output_pdf_path: str,
                           artifacts: Dict[str, Any],
                           original_ocr_text: str = "",
                           translated_text: str = "",
                           processing_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Verify overall quality of a processed page.

        Args:
            input_image_path: Path to original input image
            output_pdf_path: Path to generated PDF
            artifacts: Dictionary containing tables, charts, diagrams artifacts
            original_ocr_text: Original Japanese text extracted via OCR
            translated_text: Translated English text
            processing_results: Full results from the BookTranslator.process_page()

        Returns:
            Dictionary with quality score, issues list, and pass/fail status
        """
        issues = []

        # 1. Verify file existence
        file_issues = self._verify_files(input_image_path, output_pdf_path)
        issues.extend(file_issues)

        # 2. Check diagram quality
        if artifacts.get('diagrams'):
            diagram_issues = self._verify_diagrams(artifacts['diagrams'])
            issues.extend(diagram_issues)

        # 3. Check table completeness
        if artifacts.get('tables'):
            table_issues = self._verify_tables(artifacts['tables'])
            issues.extend(table_issues)

        # 4. Check chart accuracy
        if artifacts.get('charts'):
            chart_issues = self._verify_charts(artifacts['charts'])
            issues.extend(chart_issues)

        # 5. Check visual charts (from chart_translator)
        if artifacts.get('visual_charts'):
            visual_chart_count = artifacts['visual_charts']
            if visual_chart_count == 0 and artifacts.get('charts'):
                issues.append({
                    'type': 'chart',
                    'severity': 'warning',
                    'message': 'Charts detected but visual rendering may have failed',
                    'component': 'chart_translator'
                })

        # 6. Verify text translation quality
        if original_ocr_text and translated_text:
            text_issues = self._verify_translation(original_ocr_text, translated_text)
            issues.extend(text_issues)

        # 7. Check for processing warnings/errors in results
        if processing_results:
            processing_issues = self._verify_processing_results(processing_results)
            issues.extend(processing_issues)

        # Calculate overall quality score
        score = self._calculate_quality_score(issues)

        # Determine pass/fail (70% threshold)
        passed = score >= 70

        # Add overall assessment
        quality_level = self._get_quality_level(score)

        return {
            'score': score,
            'quality_level': quality_level,
            'issues': issues,
            'passed': passed,
            'issue_summary': self._summarize_issues(issues),
            'recommendations': self._generate_recommendations(issues)
        }

    def _verify_files(self, input_path: str, output_path: str) -> List[Dict[str, Any]]:
        """Verify that required files exist and are valid."""
        issues = []

        # Check input image
        if not os.path.exists(input_path):
            issues.append({
                'type': 'file',
                'severity': 'critical',
                'message': f'Input image not found: {input_path}',
                'component': 'filesystem'
            })
        elif os.path.getsize(input_path) == 0:
            issues.append({
                'type': 'file',
                'severity': 'critical',
                'message': 'Input image file is empty',
                'component': 'filesystem'
            })

        # Check output PDF
        if not os.path.exists(output_path):
            issues.append({
                'type': 'file',
                'severity': 'critical',
                'message': f'Output PDF not found: {output_path}',
                'component': 'pdf_generation'
            })
        elif os.path.getsize(output_path) == 0:
            issues.append({
                'type': 'file',
                'severity': 'critical',
                'message': 'Output PDF file is empty',
                'component': 'pdf_generation'
            })
        elif os.path.getsize(output_path) < 1000:  # Less than 1KB is suspicious
            issues.append({
                'type': 'file',
                'severity': 'error',
                'message': f'Output PDF unusually small ({os.path.getsize(output_path)} bytes)',
                'component': 'pdf_generation'
            })

        return issues

    def _verify_diagrams(self, diagrams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verify diagram quality and completeness."""
        issues = []

        for idx, diagram in enumerate(diagrams):
            diagram_id = diagram.get('id', f'diagram_{idx}')

            # Check annotation count
            annotations = diagram.get('annotations', [])
            if len(annotations) < self.min_diagram_labels:
                issues.append({
                    'type': 'diagram',
                    'severity': 'warning',
                    'message': f'Diagram {diagram_id} has only {len(annotations)} label(s), expected at least {self.min_diagram_labels}',
                    'component': 'diagram_agent',
                    'diagram_id': diagram_id
                })

            # Check if diagram has bounding box
            if not diagram.get('bbox') and not diagram.get('region'):
                issues.append({
                    'type': 'diagram',
                    'severity': 'error',
                    'message': f'Diagram {diagram_id} missing bounding box information',
                    'component': 'diagram_agent',
                    'diagram_id': diagram_id
                })

            # Check for empty annotations
            empty_annotations = sum(1 for ann in annotations if not ann.get('text', '').strip())
            if empty_annotations > 0:
                issues.append({
                    'type': 'diagram',
                    'severity': 'warning',
                    'message': f'Diagram {diagram_id} has {empty_annotations} empty annotation(s)',
                    'component': 'diagram_agent',
                    'diagram_id': diagram_id
                })

        return issues

    def _verify_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verify table completeness and data integrity."""
        issues = []

        for idx, table in enumerate(tables):
            table_id = table.get('id', f'table_{idx}')

            # Get table dimensions
            rows = table.get('rows', 0)
            cols = table.get('cols', 0)
            cells = table.get('cells', [])

            # Verify basic structure
            if rows == 0 or cols == 0:
                issues.append({
                    'type': 'table',
                    'severity': 'error',
                    'message': f'Table {table_id} has invalid dimensions: {rows}x{cols}',
                    'component': 'table_agent',
                    'table_id': table_id
                })
                continue

            # Check cell count
            expected_cells = rows * cols
            actual_cells = len(cells)

            if actual_cells < expected_cells:
                issues.append({
                    'type': 'table',
                    'severity': 'error',
                    'message': f'Table {table_id} missing cells: expected {expected_cells}, found {actual_cells}',
                    'component': 'table_agent',
                    'table_id': table_id
                })

            # Check for empty cells
            empty_cells = sum(1 for cell in cells if not cell.get('text', '').strip())
            empty_ratio = empty_cells / len(cells) if cells else 0

            if empty_ratio > self.max_empty_table_cells_ratio:
                issues.append({
                    'type': 'table',
                    'severity': 'warning',
                    'message': f'Table {table_id} has {empty_cells}/{len(cells)} empty cells ({empty_ratio:.1%})',
                    'component': 'table_agent',
                    'table_id': table_id,
                    'empty_cell_ratio': empty_ratio
                })

            # Check for translation completeness in cells
            untranslated_cells = sum(1 for cell in cells
                                    if cell.get('text', '').strip() and not cell.get('translation', '').strip())

            if untranslated_cells > 0:
                issues.append({
                    'type': 'table',
                    'severity': 'error',
                    'message': f'Table {table_id} has {untranslated_cells} untranslated cell(s)',
                    'component': 'table_agent',
                    'table_id': table_id
                })

        return issues

    def _verify_charts(self, charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verify chart data and visualization specs."""
        issues = []

        for idx, chart in enumerate(charts):
            chart_id = chart.get('id', f'chart_{idx}')

            # Check for visualization spec
            spec = chart.get('spec')
            if not spec:
                issues.append({
                    'type': 'chart',
                    'severity': 'error',
                    'message': f'Chart {chart_id} missing visualization spec',
                    'component': 'chart_agent',
                    'chart_id': chart_id
                })
                continue

            # Check for data in spec or meta
            meta = chart.get('meta', {})
            data_values = meta.get('data_values')

            if not data_values and not spec.get('data'):
                issues.append({
                    'type': 'chart',
                    'severity': 'error',
                    'message': f'Chart {chart_id} missing data values',
                    'component': 'chart_agent',
                    'chart_id': chart_id
                })

            # Check if spec has required fields for rendering
            if spec and not spec.get('mark'):
                issues.append({
                    'type': 'chart',
                    'severity': 'warning',
                    'message': f'Chart {chart_id} spec missing mark type',
                    'component': 'chart_agent',
                    'chart_id': chart_id
                })

        return issues

    def _verify_translation(self, original_text: str, translated_text: str) -> List[Dict[str, Any]]:
        """Verify translation quality based on text metrics."""
        issues = []

        original_len = len(original_text.strip())
        translated_len = len(translated_text.strip())

        # Check if translation exists
        if original_len > 0 and translated_len == 0:
            issues.append({
                'type': 'translation',
                'severity': 'critical',
                'message': 'No translation generated despite having original text',
                'component': 'translator'
            })
            return issues

        # Calculate translation ratio
        if original_len > 0:
            ratio = translated_len / original_len

            # English translations of Japanese are typically 0.5x to 2x the character count
            if ratio < self.min_translation_ratio:
                issues.append({
                    'type': 'translation',
                    'severity': 'warning',
                    'message': f'Translation unusually short ({ratio:.2f}x original length)',
                    'component': 'translator',
                    'translation_ratio': ratio
                })
            elif ratio > self.max_translation_ratio:
                issues.append({
                    'type': 'translation',
                    'severity': 'warning',
                    'message': f'Translation unusually long ({ratio:.2f}x original length)',
                    'component': 'translator',
                    'translation_ratio': ratio
                })

        return issues

    def _verify_processing_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for warnings or errors in processing results."""
        issues = []

        # Check for warnings in results
        warnings = results.get('warnings', [])
        for warning in warnings:
            issues.append({
                'type': 'processing',
                'severity': 'warning',
                'message': warning,
                'component': 'pipeline'
            })

        # Check individual steps
        steps = results.get('steps', {})

        # Check PDF creation step specifically
        pdf_step = steps.get('pdf_creation', {})
        if not pdf_step.get('success', True):
            issues.append({
                'type': 'processing',
                'severity': 'critical',
                'message': f"PDF creation failed: {pdf_step.get('error', 'Unknown error')}",
                'component': 'pdf_generation'
            })

        # Check for artifact processing issues
        artifacts_step = steps.get('artifacts', {})
        if artifacts_step:
            # If we expected diagrams but got none
            if results.get('diagram_regions') and artifacts_step.get('diagrams', 0) == 0:
                issues.append({
                    'type': 'processing',
                    'severity': 'warning',
                    'message': 'Diagram regions detected but no diagram artifacts generated',
                    'component': 'diagram_agent'
                })

        return issues

    def _calculate_quality_score(self, issues: List[Dict[str, Any]]) -> int:
        """Calculate overall quality score from 0-100 based on issues."""
        base_score = 100

        # Deduct points based on severity
        for issue in issues:
            severity = issue.get('severity', 'warning')
            weight = self.severity_weights.get(severity, 0)
            base_score -= weight

        # Ensure score stays in valid range
        return max(0, min(100, base_score))

    def _get_quality_level(self, score: int) -> str:
        """Get quality level description based on score."""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Acceptable"
        elif score >= 50:
            return "Poor"
        else:
            return "Failed"

    def _summarize_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Summarize issues by severity."""
        summary = {
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0
        }

        for issue in issues:
            severity = issue.get('severity', 'warning')
            summary[severity] = summary.get(severity, 0) + 1

        return summary

    def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on issues found."""
        recommendations = []

        # Group issues by component
        component_issues = {}
        for issue in issues:
            component = issue.get('component', 'unknown')
            if component not in component_issues:
                component_issues[component] = []
            component_issues[component].append(issue)

        # Generate recommendations
        if 'diagram_agent' in component_issues:
            diag_issues = component_issues['diagram_agent']
            if any(i.get('severity') in ['error', 'critical'] for i in diag_issues):
                recommendations.append("Review diagram processing - check if image quality is sufficient for label detection")

        if 'table_agent' in component_issues:
            table_issues = component_issues['table_agent']
            empty_cell_issues = [i for i in table_issues if 'empty_cell_ratio' in i]
            if empty_cell_issues:
                recommendations.append("Tables have many empty cells - verify original image quality or table structure")

        if 'chart_agent' in component_issues:
            recommendations.append("Chart processing had issues - may need to reprocess with better image quality")

        if 'translator' in component_issues:
            recommendations.append("Translation quality check failed - consider reviewing translation manually")

        if 'pdf_generation' in component_issues:
            recommendations.append("PDF generation had issues - page may need reprocessing")

        # Generic recommendation if many issues
        critical_count = sum(1 for i in issues if i.get('severity') == 'critical')
        if critical_count > 0:
            recommendations.insert(0, "CRITICAL ISSUES FOUND - Page should be reprocessed or manually reviewed")

        return recommendations


# Convenience function for easy imports
def verify_page_quality(*args, **kwargs):
    """Convenience function to verify page quality."""
    agent = QualityVerificationAgent()
    return agent.verify_page_quality(*args, **kwargs)
