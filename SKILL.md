---
name: circuit-diagram-generator
description: Generates precise circuit diagrams using LaTeX and CircuiTikZ. Use when the user requests to draw circuit diagrams from descriptions or images, especially for academic, exam, or publication purposes.
---

# Circuit Diagram Generator

## Workflow

1.  **Analyze Input**:
    *   If text: Parse the circuit topology (nodes, components, connections).
    *   If image: Use vision capabilities to identify components, labels, and layout. Note the specific shapes (e.g., rectangle vs. zig-zag resistors).
2.  **Generate Code**:
    *   Construct a complete LaTeX document using the template in `assets/template.tex`.
    *   **CRITICAL**: Ensure `\usepackage[european]{circuitikz}` is used to produce rectangular resistors.
    *   Map components to `circuitikz` commands (e.g., `R` for resistor, `L` for inductor, `C` for capacitor, `V`/`I` for sources).
3.  **Compile & Output**:
    *   Save the code to a `.tex` file.
    *   Compile to PDF using `pdflatex`.
    *   Convert to SVG using `pdf2svg` (if available) for web viewing.

## CircuiTikZ Guidelines

### Preamble
Always start with:
```latex
\documentclass[border=10pt]{standalone}
\usepackage[european]{circuitikz}
\usepackage{amsmath}
\begin{document}
\begin{circuitikz}[american voltages]
% Circuit code here
\end{circuitikz}
\end{document}
```

### Component Mapping
| Component | Style | Code Example |
|-----------|-------|--------------|
| Resistor (Rectangular) | `european` (global) | `\draw (0,0) to[R, l=$R_{ab}$] (2,0);` |
| Voltage Source | American | `\draw (0,0) to[V, v=$U$] (0,2);` |
| Current Source | American | `\draw (0,0) to[I, i=$I$] (2,0);` |
| Node | Dot | `\node[circ] at (2,2) {};` |

### Best Practices
- **Labels**: Use LaTeX math mode for labels (e.g., `l=$R_{12}$`).
- **Topology**: For bridge circuits, calculate coordinates carefully or use relative positioning `++(x,y)`.
- **Direction**: Pay attention to current arrows `i=` and voltage polarities `v=`.

## Resources

- `assets/template.tex`: Base template.
