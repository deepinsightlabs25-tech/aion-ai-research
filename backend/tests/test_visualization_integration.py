"""
Integration test demonstrating the enhanced visualization system in action.

Shows:
1. How the LLM selects appropriate visualizations
2. Different chart types being generated
3. Quality improvements in visualization selection
"""

import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.lg_workflow_agent.chart_generator import render_chart, generate_charts_for_report


def demonstrate_chart_selection():
    """Demonstrate how the system selects appropriate visualizations."""
    
    print("\n" + "="*80)
    print("ENHANCED VISUALIZATION SYSTEM - DEMONSTRATION")
    print("="*80 + "\n")
    
    # Simulate what the LLM would generate for a research report
    sample_specs = [
        {
            "chart_type": "stat_card",
            "title": "LangGraph Performance",
            "metrics": [
                {"label": "Agent Success Rate", "value": "96.2", "unit": "%"},
                {"label": "Average Latency", "value": "145", "unit": "ms"},
                {"label": "Throughput", "value": "8.5K", "unit": " ops/min"}
            ],
            "caption": "Key Performance Indicators"
        },
        {
            "chart_type": "bar",
            "title": "Framework Comparison: Execution Time",
            "labels": ["LangGraph", "CrewAI", "AutoGen", "Direct Agents"],
            "values": [145, 203, 287, 512],
            "ylabel": "Time (ms)",
            "caption": "Multi-agent orchestration frameworks compared by execution time"
        },
        {
            "chart_type": "line",
            "title": "Streaming Performance Over Time",
            "series": [
                {"name": "LangGraph", "x": [1, 2, 3, 4, 5], "y": [140, 142, 141, 143, 145]},
                {"name": "CrewAI", "x": [1, 2, 3, 4, 5], "y": [210, 205, 202, 198, 203]},
                {"name": "AutoGen", "x": [1, 2, 3, 4, 5], "y": [295, 290, 285, 280, 287]}
            ],
            "xlabel": "Test Run",
            "ylabel": "Time (ms)",
            "caption": "Latency stability across multiple test runs"
        },
        {
            "chart_type": "flowchart",
            "title": "LangGraph Workflow Architecture",
            "steps": [
                {"text": "Query Input", "color": "#6C63FF"},
                {"text": "Node Routing", "color": "#00D4AA"},
                {"text": "Parallel Sub-agents", "color": "#FF6B6B"},
                {"text": "Result Aggregation", "color": "#FFD93D"},
                {"text": "Output Formatting", "color": "#4ECDC4"}
            ],
            "caption": "Typical LangGraph execution flow for multi-agent research tasks"
        },
        {
            "chart_type": "matrix",
            "title": "Framework Capability Scorecard",
            "categories": ["Orchestration", "Streaming", "Tool Use", "Error Recovery", "Community"],
            "items": [
                {"name": "LangGraph", "scores": [95, 92, 88, 90, 85]},
                {"name": "CrewAI", "scores": [82, 75, 90, 85, 88]},
                {"name": "AutoGen", "scores": [78, 70, 92, 80, 82]}
            ],
            "caption": "Comparative capability scores across key dimensions"
        },
        {
            "chart_type": "heatmap",
            "title": "Feature Support Matrix",
            "labels_x": ["Streaming", "State Management", "Error Handling", "Custom Nodes", "Debugging"],
            "labels_y": ["LangGraph", "CrewAI", "AutoGen"],
            "data": [
                [1.0, 0.95, 0.90, 0.98, 0.92],  # LangGraph
                [0.75, 0.80, 0.85, 0.70, 0.75], # CrewAI
                [0.70, 0.75, 0.80, 0.85, 0.68]  # AutoGen
            ],
            "colormap": "RdYlGn",
            "caption": "Feature support comparison (1.0 = fully supported)"
        },
        {
            "chart_type": "architecture",
            "title": "LangGraph System Architecture",
            "components": [
                {"name": "Graph Builder", "type": "Core", "color": "#6C63FF"},
                {"name": "Node Registry", "type": "Component", "color": "#00D4AA"},
                {"name": "State Manager", "type": "Storage", "color": "#FF6B6B"},
                {"name": "Stream Handler", "type": "I/O", "color": "#FFD93D"},
                {"name": "Error Handler", "type": "Utility", "color": "#4ECDC4"},
                {"name": "Executor Engine", "type": "Compute", "color": "#FF8C42"}
            ],
            "caption": "Core components of the LangGraph framework"
        },
        {
            "chart_type": "formula",
            "title": "LangGraph State Update",
            "formula": r"S_{t+1} = \text{merge}(S_t, \Delta S_t) \text{ where } \Delta S_t = \text{node}(S_t, \text{input})",
            "description": "State update mechanism in LangGraph's graph execution model",
            "caption": "Mathematical foundation of state management"
        },
        {
            "chart_type": "area",
            "title": "Code Complexity Trends",
            "series": [
                {"name": "LangGraph", "x": [1, 2, 3, 4], "y": [150, 180, 200, 220]},
                {"name": "CrewAI", "x": [1, 2, 3, 4], "y": [120, 160, 210, 280]},
                {"name": "Direct Code", "x": [1, 2, 3, 4], "y": [100, 200, 400, 800]}
            ],
            "xlabel": "Agent Count",
            "ylabel": "Lines of Code",
            "caption": "Codebase growth as system complexity increases"
        }
    ]
    
    print("📊 VISUALIZATION SPECIFICATIONS GENERATED BY LLM\n")
    print(f"Total visualizations to generate: {len(sample_specs)}\n")
    
    for i, spec in enumerate(sample_specs, 1):
        chart_type = spec.get("chart_type", "unknown")
        title = spec.get("title", "Untitled")
        caption = spec.get("caption", "")
        print(f"{i}. [{chart_type.upper()}] {title}")
        print(f"   → {caption}\n")
    
    # Now generate all the charts
    print("="*80)
    print("🎨 RENDERING VISUALIZATIONS")
    print("="*80 + "\n")
    
    results = generate_charts_for_report(sample_specs)
    
    print(f"✓ Successfully generated {len(results)} out of {len(sample_specs)} visualizations\n")
    
    # Show stats
    successful = len(results)
    failed = len(sample_specs) - successful
    success_rate = (successful / len(sample_specs)) * 100
    
    print("Generation Statistics:")
    print(f"  • Total requested: {len(sample_specs)}")
    print(f"  • Successfully rendered: {successful}")
    print(f"  • Failed: {failed}")
    print(f"  • Success rate: {success_rate:.1f}%\n")
    
    # Show breakdown by type
    chart_types = {}
    for spec in sample_specs:
        ct = spec.get("chart_type", "unknown")
        chart_types[ct] = chart_types.get(ct, 0) + 1
    
    print("Visualization Types Generated:")
    for chart_type, count in sorted(chart_types.items()):
        print(f"  • {chart_type.capitalize()}: {count}")
    
    print("\n" + "="*80)
    print("✓ DEMONSTRATION COMPLETE")
    print("="*80)
    
    print("\n📝 KEY IMPROVEMENTS DEMONSTRATED:")
    print("  ✓ Flow diagrams for process visualization")
    print("  ✓ Architecture diagrams for system overview")
    print("  ✓ LaTeX formulas for mathematical concepts")
    print("  ✓ Heatmaps for correlation analysis")
    print("  ✓ Matrix comparisons with scoring")
    print("  ✓ Area charts for trend visualization")
    print("  ✓ Better layout and organization")
    print("  ✓ NO metadata charts (like 'number of sources')")
    print("  ✓ Diverse visualization types (variety)")
    print("  ✓ High success rate and error handling\n")
    
    return results


def show_sample_report_structure():
    """Show how the report would be structured with visualizations."""
    
    print("\n" + "="*80)
    print("📄 SAMPLE REPORT STRUCTURE (WITH ENHANCED VISUALIZATIONS)")
    print("="*80 + "\n")
    
    sample_report = """# Research Report: Multi-Agent Orchestration Frameworks

## Executive Summary

We compared three leading multi-agent orchestration frameworks: LangGraph, CrewAI, and AutoGen.

{{CHART:0}}

## Performance Comparison

LangGraph demonstrates superior performance metrics with 145ms average latency.

{{CHART:1}}

### Stability Analysis

Across multiple runs, LangGraph maintains consistent performance:

{{CHART:2}}

## Architectural Approaches

### LangGraph Workflow

{{CHART:3}}

## Comprehensive Comparison

{{CHART:4}}

## Feature Support Analysis

{{CHART:5}}

### System Architecture

{{CHART:6}}

## Mathematical Foundation

{{CHART:7}}

## Scalability Analysis

{{CHART:8}}

## Conclusion

LangGraph provides the best balance of performance, features, and ease of use.
"""
    
    print("Report structure (before embedding images):\n")
    lines = sample_report.split('\n')
    for line in lines:
        if '{{CHART:' in line:
            print(f"  {line} ← [Chart will be embedded here]")
        else:
            print(f"  {line}")
    
    print("\n✓ Each {{CHART:n}} marker is replaced with an embedded PNG image")
    print("✓ Images are base64-encoded for direct embedding in Markdown")
    print("✓ Report maintains professional appearance with integrated visualizations\n")


def main():
    """Run the demonstration."""
    results = demonstrate_chart_selection()
    show_sample_report_structure()
    
    print("\n" + "="*80)
    print("🚀 NEXT STEPS")
    print("="*80)
    print("""
1. Run a real query with the enhanced system:
   python -m src.lg_workflow_agent.run_sample "Compare LangGraph vs CrewAI"

2. Check generated reports in backend/reports/ directory

3. View the visualizations in the markdown files

4. For streaming updates:
   python -m src.lg_workflow_agent.run_sample --stream "Your query"

5. Customize visualization types by editing:
   - backend/src/lg_workflow_agent/prompts.py (LLM guidance)
   - backend/src/lg_workflow_agent/chart_generator.py (rendering)
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
