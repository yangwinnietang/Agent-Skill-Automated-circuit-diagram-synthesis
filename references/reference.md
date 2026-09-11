# CircuiTikZ working reference

Use the installed version's manual (`texdoc circuitikz`) for details. The [official project](https://circuitikz.github.io/circuitikz/) links its [HTML manual](https://rmano.github.io/circuitikz/). Syntax below is exercised by `assets/examples/` on the versions recorded in `TESTING.md`.

## Styles and two-terminal components

Select styles independently, e.g. `european resistors,american inductors,american voltages,american currents`. To use zigzag resistors change only `european resistors` to `american resistors`. A resistor style does not determine the voltage-source symbol or annotation convention.

| Element | Path syntax | Meaning to verify |
|---|---|---|
| Resistor | `(a) to[R,l=$R_1$] (b)` | Terminal nets a and b |
| Capacitor | `(a) to[C,l=$C_1$] (b)` | Preserve polar/nonpolar choice |
| Inductor | `(a) to[L,l=$L_1$] (b)` | Winding and any specified coupling |
| Voltage source | `(a) to[V,invert,l={$V_1$}] (b)` | With the bundled options, positive at b, negative at a; inspect signs |
| Current source | `(a) to[I,l=$I_1$] (b)` | Internal arrow from a toward b in the bundled convention |
| Diode | `(a) to[D,l=$D_1$] (b)` | Anode a, cathode b without inversion |
| Open switch | `(a) to[spst,l=$S_1$] (b)` | Draws an open switch; do not silently close it |
| Wire | `(a) -- (b)` | All points on a continuous wire share a net |
| Open terminal | `node[ocirc] {}` | Terminal marker, not ground |
| Junction | `node[circ] {}` or path `*-*` | Only mark actual connections |
| Ground | `node[ground] {}` | Use only for a specified reference net |

Brace label values, especially when they contain `=` or commas: `l={$R_1=10\,\mathrm{k}\Omega$}`. Unbraced `l=$R_1=10...$` can fail PGF key parsing.

Use `l_=` to move a component label to the other side. `i>^=` and `i<^=` set reference-current direction and placement; they are annotations, not simulation results. Voltage `v=`, `v^=`, `v_=` and `<`/`>` conventions depend on element type and voltage convention. `invert` changes an element's orientation. After changing direction, inspect the signs and arrows instead of copying a polarity rule across all element types.

## Multi-pin elements

```latex
\node[op amp] (U1) at (4,2) {$U_1$};
\draw (0,2 |- U1.-) to[R,l=$R_{in}$] (U1.-);
\draw (U1.+) -- ++(-0.5,0) node[ground] {};
\draw (U1.out) -- ++(1,0) coordinate (out);
```

Use `(U1.up)` and `(U1.down)` for supply pins when specified. An ideal signal-only op-amp diagram may omit supply wiring if that abstraction is explicit. Route feedback to the correct signed input.

```latex
\node[npn] (Q1) at (3,2) {$Q_1$};
\draw (Q1.B) -- ++(-1,0);
\draw (Q1.C) -- ++(0,1);
\draw (Q1.E) -- ++(0,-1);
```

MOSFETs use the chosen symbol's documented `G`, `D`, `S`, and sometimes `B` anchors. Verify body connection and body diode when present. Logic nodes such as `and port` use `in 1`, `in 2`, `out`; they are not two-terminal `to[...]` elements.

## Connectivity and layout

- Name nodes once: `\coordinate (mid) at (4,3);`. Connect to `(mid)`, not a nearby guessed coordinate.
- `|-` and `-|` construct orthogonal routes. Their corners do not add electrical nodes unless a branch connects there.
- A crossing without a dot is not a junction in the selected convention. For clarity, route around crossings or use a jump (`to[crossing]`) as demonstrated in `crossings.tex`.
- Repeated ground or net labels imply connections only when intended. A layout tool cannot validate this implication electrically.
- In bridge circuits, keep the two midpoint nets separate unless a specified element or wire joins them. In a divider, output is the resistor junction, not the supply rail.
- `node[ground]` draws a symbol; it neither simulates a reference potential nor fixes a disconnected wire.

## Troubleshooting

| Symptom | Action |
|---|---|
| Command exists, compilation fails | Read log; check format files, `standalone`, `circuitikz`, PGF, fonts |
| `ctex.sty` / Fandol missing | Install Chinese language support; use the default template for non-Chinese diagrams |
| Missing character or Unicode error | Select suitable engine and covering font; never accept omitted labels |
| Unknown PGF key / shape | Verify against the installed manual; do not invent a substitute symbol |
| SVG/PNG failure | Check Poppler, page count, and converter log; PDF-only mode is explicit |
| Repeated unresolved-reference warning | Check labels or use `--passes 3`; report unresolved warnings |
| Overlapping label | Move label or expand coordinates, then recheck topology |

The helper disables shell escape and bounds subprocess time. TeX can still read files accessible to its process; these measures do not make arbitrary uploaded TeX safe to execute.
