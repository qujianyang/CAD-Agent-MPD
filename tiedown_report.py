"""
Tie-down report generation -- assembles the SAR 'Appendix G' section from a
validated TiedownReport.

Deterministic: every number comes from tiedown_engine (the validated engine),
never from an LLM. The text is fixed boilerplate with the computed values
inserted, so the output is reproducible and certifiable.
"""
from datetime import date as _date

from tiedown_engine import format_full_report_table


def generate_appendix_g(report, *, project: str = "Project Spinel",
                        variant: str = "Variant E-2", standard: str = "MIL-STD-209K",
                        report_date: str = None) -> str:
    """
    Build the Appendix G section (Markdown) from a TiedownReport.

    The required minimum safety factor is taken from report.target_SF.
    Numbers (table + min SF + pass count) come straight from the engine.
    """
    L = report.loads
    target = report.target_SF
    n = len(report.items)
    failing = [r for r in report.items if not r.passed(target)]
    n_pass = n - len(failing)
    governing = min(report.items, key=lambda r: r.min_SF) if report.items else None
    d = report_date or _date.today().isoformat()

    lines = [
        "# Appendix G - Tie-Down Provision Analysis",
        "",
        f"*{project}, {variant}  |  {d}*",
        "",
        "## G.1  Scope and Basis",
        "",
        f"The tie-down provision has been assessed in accordance with {standard} "
        f"(Interface Standard for Lifting and Tie-Down Provisions). Each secured item is "
        f"analysed against the transport design loads of {L.long_G:g}G longitudinal, "
        f"{L.vert_G:g}G vertical and {L.lat_G:g}G lateral (g = {L.g} m/s^2), applied as "
        f"multiples of the item weight.",
        "",
        "For each fastener the safety factor on each axis is "
        "`SF = yield force / (design force / quantity)`, where the mounting face "
        "determines whether the fastener is loaded in tension or shear. An item is "
        f"assessed as satisfactory when its minimum safety factor across the three axes "
        f"is not less than the required design factor of {target:g}.",
        "",
        "## G.2  Results",
        "",
        "```",
        format_full_report_table(report),
        "```",
        "",
        "## G.3  Assessment",
        "",
    ]

    if governing is None:
        lines.append("No items were analysed.")
        lines.append("")
        return "\n".join(lines)

    gov_axis = governing.limiting_axis.axis
    lines.append(
        f"A total of {n} items were analysed. {n_pass} of {n} items meet the required "
        f"minimum safety factor of {target:g}. The lowest safety factor across all items "
        f"is {governing.min_SF:.3f}, occurring on the {gov_axis} axis of "
        f'"{governing.item.name}".'
    )
    lines.append("")
    if failing:
        names = "; ".join(
            f"{r.item.name} (min SF {r.min_SF:.3f})"
            for r in sorted(failing, key=lambda r: r.min_SF)
        )
        lines.append(
            f"The following item(s) do NOT meet the required factor of {target:g} and "
            f"require review: {names}."
        )
    else:
        lines.append(
            f"All tie-down provisions meet the required factor of {target:g} and are "
            f"therefore assessed to be satisfactory."
        )
    lines.append("")
    return "\n".join(lines)
