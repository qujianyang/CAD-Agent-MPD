# MIL-STD-810H Method 516.8: Classical Shock Pulse Shapes

**Source:** MIL-STD-810H, Method 516.8, method page 516.8-12, classical shock
pulse guidance. This summary is based on the project copy of
`MIL-STD-810H.pdf`.

## Recognized pulse descriptions

Method 516.8 discusses half-sine, terminal-peak sawtooth, and trapezoidal
classical shock pulses. These may be derived from a measured time history,
scaled measurements, structural analysis, or a justified combination of these
sources.

## Substituting one pulse shape for another

When a classical pulse is substituted for another specification, the method
requires the amplitude to be adjusted so that the substituted pulse has an
equivalent velocity change. The substitution and any potential over-test or
under-test must be documented and approved.

## Project interpretation

The agent exposes `pulse_shape`, `input_g`, and `to_ms` as explicit inputs.
For a terminal-peak sawtooth, the physics tool calculates the corresponding
velocity change before evaluating isolator response. Do not silently replace a
user's pulse shape or duration; ask for clarification or use only documented
project defaults.

## Use in answers

Use this source for questions about the difference between sawtooth and
half-sine pulses, or why pulse duration must be supplied with peak G.
