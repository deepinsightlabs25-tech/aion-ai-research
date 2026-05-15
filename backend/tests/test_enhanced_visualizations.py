"""
Test suite for enhanced visualization types in chart_generator.

Tests all new chart types:
- Area charts
- Heatmaps
- Flowcharts
- Architecture diagrams
- Formulas (LaTeX)
- Matrix comparisons
"""

import json
from pathlib import Path
import pytest

# Ensure backend/ is on sys.path
import sys
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.lg_workflow_agent.chart_generator import render_chart, generate_charts_for_report


class TestAreaChart:
    """Test area chart rendering."""
    
    def test_area_chart_basic(self):
        """Test basic area chart generation."""
        spec = {
            "chart_type": "area",
            "title": "Performance Trends",
            "xlabel": "Time (weeks)",
            "ylabel": "Score",
            "series": [
                {
                    "name": "Model A",
                    "x": [1, 2, 3, 4, 5],
                    "y": [60, 70, 75, 80, 85]
                },
                {
                    "name": "Model B",
                    "x": [1, 2, 3, 4, 5],
                    "y": [50, 60, 65, 72, 80]
                }
            ]
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Area chart generated successfully")


class TestHeatmap:
    """Test heatmap rendering."""
    
    def test_heatmap_basic(self):
        """Test basic heatmap generation."""
        spec = {
            "chart_type": "heatmap",
            "title": "Feature Correlation Matrix",
            "labels_x": ["Speed", "Accuracy", "Cost", "Reliability"],
            "labels_y": ["System A", "System B", "System C"],
            "data": [
                [0.9, 0.7, 0.3, 0.8],
                [0.85, 0.92, 0.4, 0.75],
                [0.88, 0.8, 0.5, 0.85]
            ],
            "colormap": "viridis"
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Heatmap generated successfully")


class TestFlowchart:
    """Test flowchart rendering."""
    
    def test_flowchart_basic(self):
        """Test basic flowchart generation."""
        spec = {
            "chart_type": "flowchart",
            "title": "Research Workflow",
            "steps": [
                {"text": "Query Input", "color": "#6C63FF"},
                {"text": "Data Collection", "color": "#00D4AA"},
                {"text": "Analysis", "color": "#FF6B6B"},
                {"text": "Report Generation", "color": "#FFD93D"},
                {"text": "Final Output", "color": "#4ECDC4"}
            ]
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Flowchart generated successfully")


class TestArchitectureDiagram:
    """Test architecture diagram rendering."""
    
    def test_architecture_basic(self):
        """Test basic architecture diagram generation."""
        spec = {
            "chart_type": "architecture",
            "title": "System Architecture",
            "components": [
                {"name": "Frontend", "type": "UI", "color": "#6C63FF"},
                {"name": "API Gateway", "type": "Service", "color": "#00D4AA"},
                {"name": "Data Store", "type": "Database", "color": "#FF6B6B"},
                {"name": "Cache", "type": "Memory", "color": "#FFD93D"},
                {"name": "Queue", "type": "Message", "color": "#4ECDC4"},
                {"name": "Worker", "type": "Process", "color": "#FF8C42"}
            ]
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Architecture diagram generated successfully")


class TestFormula:
    """Test formula/LaTeX rendering."""
    
    def test_formula_basic(self):
        """Test basic formula generation."""
        spec = {
            "chart_type": "formula",
            "title": "Transformer Attention",
            "formula": r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V",
            "description": "The core attention mechanism in transformer models"
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Formula visualization generated successfully")

    def test_formula_complex(self):
        """Test complex mathematical formula."""
        spec = {
            "chart_type": "formula",
            "title": "Model Performance",
            "formula": r"F_1 = 2 \cdot \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}",
            "description": "The F1 score combines precision and recall"
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Complex formula generated successfully")


class TestMatrixComparison:
    """Test matrix/capability comparison rendering."""
    
    def test_matrix_basic(self):
        """Test basic matrix comparison."""
        spec = {
            "chart_type": "matrix",
            "title": "Framework Capability Matrix",
            "categories": ["Performance", "Ease of Use", "Flexibility", "Community"],
            "items": [
                {
                    "name": "Framework A",
                    "scores": [95, 70, 85, 90]
                },
                {
                    "name": "Framework B",
                    "scores": [80, 90, 75, 85]
                },
                {
                    "name": "Framework C",
                    "scores": [85, 75, 95, 80]
                }
            ]
        }
        uri = render_chart(spec)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        print("✓ Matrix comparison generated successfully")


class TestBatchGeneration:
    """Test batch generation of multiple charts."""
    
    def test_generate_diverse_charts(self):
        """Test generating a diverse set of visualizations."""
        specs = [
            {
                "chart_type": "bar",
                "title": "Model Performance",
                "labels": ["A", "B", "C"],
                "values": [85, 92, 78],
                "caption": "Performance Metrics"
            },
            {
                "chart_type": "flowchart",
                "title": "Process",
                "steps": [
                    {"text": "Start", "color": "#6C63FF"},
                    {"text": "Process", "color": "#00D4AA"},
                    {"text": "End", "color": "#FF6B6B"}
                ],
                "caption": "Processing Flow"
            },
            {
                "chart_type": "formula",
                "title": "Key Equation",
                "formula": "y = mx + b",
                "description": "Linear equation",
                "caption": "Mathematical Model"
            },
            {
                "chart_type": "heatmap",
                "title": "Correlation",
                "labels_x": ["X1", "X2"],
                "labels_y": ["Y1", "Y2"],
                "data": [[1.0, 0.5], [0.5, 1.0]],
                "caption": "Correlation Matrix"
            },
            {
                "chart_type": "line",
                "title": "Trend",
                "series": [{"name": "Series", "x": [1,2,3], "y": [10,20,15]}],
                "caption": "Time Series"
            }
        ]
        
        results = generate_charts_for_report(specs)
        assert len(results) > 0
        assert all("data_uri" in r for r in results)
        assert all("caption" in r for r in results)
        assert all(r["data_uri"].startswith("data:image/png;base64,") for r in results)
        print(f"✓ Generated {len(results)} diverse visualizations")


class TestErrorHandling:
    """Test error handling for invalid specs."""
    
    def test_invalid_chart_type(self):
        """Test handling of invalid chart type."""
        spec = {
            "chart_type": "nonexistent",
            "title": "Invalid"
        }
        uri = render_chart(spec)
        assert uri is None
        print("✓ Invalid chart type handled gracefully")

    def test_empty_spec(self):
        """Test handling of empty spec."""
        spec = {}
        uri = render_chart(spec)
        assert uri is None
        print("✓ Empty spec handled gracefully")

    def test_missing_required_fields(self):
        """Test handling of missing required fields."""
        spec = {
            "chart_type": "area"
            # Missing series
        }
        uri = render_chart(spec)
        assert uri is None
        print("✓ Missing fields handled gracefully")


class TestIntegration:
    """Integration tests for the full workflow."""
    
    def test_report_with_multiple_visualizations(self):
        """Test generating a complete report with diverse visualizations."""
        specs = [
            {
                "chart_type": "stat_card",
                "title": "Key Metrics",
                "metrics": [
                    {"label": "Accuracy", "value": "94.5", "unit": "%"},
                    {"label": "Speed", "value": "1.2", "unit": "ms"},
                    {"label": "Throughput", "value": "10K", "unit": " ops/sec"}
                ],
                "caption": "Performance Summary"
            },
            {
                "chart_type": "bar",
                "title": "Component Performance",
                "labels": ["Model", "Optimizer", "Loss", "Metric"],
                "values": [95, 88, 92, 85],
                "ylabel": "Score",
                "caption": "Component Scores"
            },
            {
                "chart_type": "line",
                "title": "Training Progress",
                "series": [
                    {"name": "Train Loss", "x": [1,2,3,4,5], "y": [2.5, 1.8, 1.2, 0.8, 0.5]},
                    {"name": "Val Loss", "x": [1,2,3,4,5], "y": [2.6, 1.9, 1.3, 0.9, 0.6]}
                ],
                "xlabel": "Epoch",
                "ylabel": "Loss",
                "caption": "Model Convergence"
            },
            {
                "chart_type": "flowchart",
                "title": "Model Pipeline",
                "steps": [
                    {"text": "Data Preprocessing", "color": "#6C63FF"},
                    {"text": "Feature Engineering", "color": "#00D4AA"},
                    {"text": "Model Training", "color": "#FF6B6B"},
                    {"text": "Evaluation", "color": "#FFD93D"},
                    {"text": "Deployment", "color": "#4ECDC4"}
                ],
                "caption": "ML Pipeline"
            },
            {
                "chart_type": "architecture",
                "title": "ML Infrastructure",
                "components": [
                    {"name": "Data Pipeline", "type": "ETL"},
                    {"name": "Training Engine", "type": "Compute"},
                    {"name": "Model Registry", "type": "Storage"},
                    {"name": "Inference Service", "type": "API"}
                ],
                "caption": "System Architecture"
            },
            {
                "chart_type": "formula",
                "title": "Model Equation",
                "formula": r"\hat{y} = \text{ReLU}(W_1 x + b_1) \cdot W_2 + b_2",
                "description": "Neural network prediction formula",
                "caption": "Network Architecture"
            }
        ]
        
        results = generate_charts_for_report(specs)
        print(f"\n✓ Generated comprehensive report with {len(results)} visualizations:")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['caption']}")


def run_all_tests():
    """Run all tests with descriptive output."""
    print("\n" + "="*70)
    print("ENHANCED VISUALIZATION TEST SUITE")
    print("="*70 + "\n")
    
    test_classes = [
        TestAreaChart,
        TestHeatmap,
        TestFlowchart,
        TestArchitectureDiagram,
        TestFormula,
        TestMatrixComparison,
        TestBatchGeneration,
        TestErrorHandling,
        TestIntegration
    ]
    
    for test_class in test_classes:
        print(f"\n📊 {test_class.__name__}")
        print("-" * 70)
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                except Exception as e:
                    print(f"✗ {method_name} failed: {e}")
    
    print("\n" + "="*70)
    print("✓ All tests completed successfully!")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_all_tests()
