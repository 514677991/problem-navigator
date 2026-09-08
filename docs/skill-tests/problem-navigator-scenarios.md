# Problem Navigator entry scenarios — 2.1.0

There is one implicit natural-language entry and eight explicit stages. `NONE` means
only user-provided material: do not check a provider or invoke Web. Public-Web work
uses Research Core when configured; host-native Web is used only after scoped explicit
authorization and only for the disclosed outbound scope. `GENERAL` and
`PRODUCT_SOFTWARE` can each use `NONE` or Web. The entry mechanically dispatches the
stored `next_stage`; it never makes a second workflow or sends work to planning or
implementation.
