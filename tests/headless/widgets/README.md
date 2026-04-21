# Channel-C Lua Widgets

BAR Lua widgets loaded into a headless match to observe the effects of
the 11 Channel-C `AICommand` arms (`draw_add_point`, `draw_add_line`,
`draw_remove_point`, `create_spline_figure`, `create_line_figure`,
`set_figure_position`, `set_figure_color`, `remove_figure`,
`draw_unit`, `group_add_unit`, `group_remove_unit`).

Each widget records call records retrievable from the headless driver
via `InvokeCallback` under a well-known name. See
`specs/002-live-headless-e2e/contracts/aicommand-arm-map.md` Channel C.

Widget files are populated by Phase 7 (US5) tasks T044 et al.
