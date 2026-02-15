# Circuit Diagram Generator

![Circuit Diagram Example](https://raw.githubusercontent.com/yangwinnietang/Agent-Skill-Automated-circuit-diagram-synthesis/main/photo.png)

## Overview

This is a skill for automatically generating high-quality circuit diagrams using LaTeX and CircuiTikZ. It enables the generation of precise, vector-based circuit diagrams from text descriptions or images.

## Features

- **LaTeX-based rendering**: Produces publication-quality circuit diagrams
- **CircuiTikZ support**: Uses the powerful `circuitikz` package for schematic drawing
- **European (rectangular) resistor symbols**: Follows academic standards by default
- **Image to circuit**: Can analyze circuit images and generate LaTeX code

## Installation

Copy the `SKILL.md` file to your skill directory to use this circuit diagram generation capability.

## Usage

When you need to draw a circuit diagram, simply describe the circuit or provide an image. The skill will:

1. **Analyze Input**: Parse circuit topology from text or identify components from images
2. **Generate Code**: Construct LaTeX code using the `circuitikz` package
3. **Compile & Output**: Generate PDF/SVG output

## Component Mapping

| Component | Style | Code Example |
|-----------|-------|--------------|
| Resistor (Rectangular) | European | `\draw (0,0) to[R, l=$R_{ab}$] (2,0);` |
| Voltage Source | American | `\draw (0,0) to[V, v=$U$] (0,2);` |
| Current Source | American | `\draw (0,0) to[I, i=$I$] (2,0);` |
| Node | Dot | `\node[circ] at (2,2) {};` |

## Project Structure

```
circuit-diagram-generator/
├── SKILL.md              # Skill definition and usage guide
├── photo.png             # Example circuit diagram
├── assets/
│   ├── README.txt        # Asset files documentation
│   └── template.tex      # LaTeX template for circuits
├── references/
│   └── reference.md     # Reference materials
└── scripts/
    ├── compile_circuit.py  # Circuit compilation script
    └── example.py           # Usage examples
```

## Example

```latex
\documentclass[border=10pt]{standalone}
\usepackage[european]{circuitikz}
\usepackage{amsmath}
\begin{document}
\begin{circuitikz}[american voltages]
\draw (0,0) to[R, l=$R_1$] (2,0) to[V, v=$U$] (2,2) to (0,2);
\end{circuitikz}
\end{document}
```

## Requirements

- LaTeX distribution (TeX Live, MiKTeX, etc.)
- `circuitikz` package
- Python 3.x (for compilation scripts)

## License

MIT License
