# Verified circuit gallery

Twelve valued circuits: editable source, three export formats, explicit terminal maps, and reproducible ideal-model comparisons.

[Verification method](../validation/analytic-reference.md) · [Visual inspection record](../validation/visual-review.md) · [Machine summary](summary.json)

| Circuit | DC output (V) | Analyses | Detail and downloads |
|---|---:|---:|---|
| Balanced Wheatstone bridge | 0 | 1 | [bridge-balanced](bridge-balanced/README.md) |
| Unbalanced Wheatstone bridge | 0.4132231405 | 1 | [bridge-unbalanced](bridge-unbalanced/README.md) |
| Loaded voltage divider | 1.666666667 | 1 | [divider-loaded](divider-loaded/README.md) |
| Unloaded voltage divider | 2.5 | 1 | [divider-unloaded](divider-unloaded/README.md) |
| Inverting amplifier | -0.9999890001 | 1 | [opamp-inverting](opamp-inverting/README.md) |
| Noninverting amplifier | 1.0999879 | 1 | [opamp-noninverting](opamp-noninverting/README.md) |
| Inverting weighted summer | -0.399999 | 1 | [opamp-summer](opamp-summer/README.md) |
| Parallel resistors with upward current source | 2 | 1 | [parallel-current](parallel-current/README.md) |
| RC high-pass filter | 0 | 4 | [rc-highpass](rc-highpass/README.md) |
| RC low-pass filter | 1 | 4 | [rc-lowpass](rc-lowpass/README.md) |
| RL low-pass, output across series resistor | 1 | 4 | [rl-lowpass](rl-lowpass/README.md) |
| Series RLC, output across resistor | 0 | 4 | [series-rlc](series-rlc/README.md) |

Regenerate with `python scripts/build_gallery.py --output-dir build/gallery`. Use `--overwrite` only to replace a previous generated gallery.
