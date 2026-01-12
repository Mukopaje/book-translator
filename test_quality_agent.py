"""
Test script for Quality Verification Agent
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.quality_agent import QualityVerificationAgent


def test_quality_agent():
    """Test the quality verification agent with sample data."""

    print("Testing Quality Verification Agent...")
    print("=" * 60)

    agent = QualityVerificationAgent()

    # Test Case 1: Good quality page
    print("\n1. Testing GOOD quality page (diagrams with labels, complete tables)...")

    good_artifacts = {
        'diagrams': [
            {
                'id': 'diagram_1',
                'bbox': {'x': 100, 'y': 100, 'w': 400, 'h': 300},
                'annotations': [
                    {'text': 'Intake Valve', 'x': 120, 'y': 150},
                    {'text': 'Piston', 'x': 250, 'y': 250},
                    {'text': 'Exhaust Valve', 'x': 350, 'y': 150}
                ]
            }
        ],
        'tables': [
            {
                'id': 'table_1',
                'rows': 5,
                'cols': 3,
                'cells': [
                    {'row': 0, 'col': 0, 'text': 'Part', 'translation': 'Part'},
                    {'row': 0, 'col': 1, 'text': 'Code', 'translation': 'Code'},
                    {'row': 0, 'col': 2, 'text': 'Qty', 'translation': 'Qty'},
                    {'row': 1, 'col': 0, 'text': 'ボルト', 'translation': 'Bolt'},
                    {'row': 1, 'col': 1, 'text': 'B123', 'translation': 'B123'},
                    {'row': 1, 'col': 2, 'text': '4', 'translation': '4'},
                    # ... more cells
                ] + [{'row': i, 'col': j, 'text': f'data_{i}_{j}', 'translation': f'data_{i}_{j}'}
                     for i in range(2, 5) for j in range(3)]
            }
        ],
        'charts': [
            {
                'id': 'chart_1',
                'spec': {'mark': 'bar', 'encoding': {}},
                'meta': {'data_values': [{'x': 1, 'y': 10}]}
            }
        ]
    }

    result = agent.verify_page_quality(
        input_image_path="test_input.jpg",  # Fictional path for test
        output_pdf_path="test_output.pdf",  # Fictional path for test
        artifacts=good_artifacts,
        original_ocr_text="これはテストテキストです。" * 20,  # ~40 chars
        translated_text="This is test text. " * 20  # ~38 chars
    )

    print(f"  Quality Score: {result['score']}/100")
    print(f"  Quality Level: {result['quality_level']}")
    print(f"  Passed: {result['passed']}")
    print(f"  Issues: {len(result['issues'])}")
    if result['issues']:
        for issue in result['issues']:
            print(f"    - [{issue['severity']}] {issue['message']}")

    # Test Case 2: Poor quality page
    print("\n2. Testing POOR quality page (few labels, empty table cells, missing data)...")

    poor_artifacts = {
        'diagrams': [
            {
                'id': 'diagram_1',
                'bbox': {'x': 100, 'y': 100, 'w': 400, 'h': 300},
                'annotations': [
                    {'text': '1', 'x': 120, 'y': 150}  # Only 1 label
                ]
            }
        ],
        'tables': [
            {
                'id': 'table_1',
                'rows': 5,
                'cols': 3,
                'cells': [
                    {'row': 0, 'col': 0, 'text': 'Header1', 'translation': 'Header1'},
                    {'row': 0, 'col': 1, 'text': '', 'translation': ''},  # Empty
                    {'row': 0, 'col': 2, 'text': '', 'translation': ''},  # Empty
                    {'row': 1, 'col': 0, 'text': '', 'translation': ''},  # Empty
                    {'row': 1, 'col': 1, 'text': 'data', 'translation': 'data'},
                    {'row': 1, 'col': 2, 'text': '', 'translation': ''},  # Empty
                ] + [{'row': i, 'col': j, 'text': '', 'translation': ''}
                     for i in range(2, 5) for j in range(3)]  # All empty
            }
        ],
        'charts': [
            {
                'id': 'chart_1',
                'spec': None,  # Missing spec
                'meta': {}
            }
        ]
    }

    result = agent.verify_page_quality(
        input_image_path="test_input.jpg",
        output_pdf_path="test_output.pdf",
        artifacts=poor_artifacts,
        original_ocr_text="これはテストテキストです。" * 100,  # 200 chars
        translated_text="Short translation"  # Only 18 chars (ratio too low)
    )

    print(f"  Quality Score: {result['score']}/100")
    print(f"  Quality Level: {result['quality_level']}")
    print(f"  Passed: {result['passed']}")
    print(f"  Issues: {len(result['issues'])}")
    if result['issues']:
        for issue in result['issues'][:5]:  # Show first 5 issues
            print(f"    - [{issue['severity']}] {issue['message']}")
        if len(result['issues']) > 5:
            print(f"    ... and {len(result['issues']) - 5} more issues")

    print(f"\n  Recommendations:")
    for rec in result['recommendations']:
        print(f"    - {rec}")

    # Test Case 3: Critical failures
    print("\n3. Testing CRITICAL failures (missing files)...")

    result = agent.verify_page_quality(
        input_image_path="nonexistent_input.jpg",
        output_pdf_path="nonexistent_output.pdf",
        artifacts={},
        original_ocr_text="",
        translated_text=""
    )

    print(f"  Quality Score: {result['score']}/100")
    print(f"  Quality Level: {result['quality_level']}")
    print(f"  Passed: {result['passed']}")
    print(f"  Critical Issues: {sum(1 for i in result['issues'] if i['severity'] == 'critical')}")

    print("\n" + "=" * 60)
    print("✅ Quality Agent Testing Complete!")


if __name__ == "__main__":
    test_quality_agent()
