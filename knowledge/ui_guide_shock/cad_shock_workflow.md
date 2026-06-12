# CAD + Shock Workflow (SolidWorks extraction)

The **CAD + Shock** tab replaces typed-in weights with live SolidWorks data: it extracts
mass, bounding box and centre of mass from an assembly, then runs the same 4-case isolator
selection automatically.

## Choosing the CAD source

Two options at the top-left:

- **"Use active SolidWorks document"** — SolidWorks must be open with the target assembly
  as the active document.
- **"Specify a file path"** — click **"📂 Browse…"** (native file dialog) or paste an
  absolute path to a `.SLDASM` or `.SLDPRT` file.

The mount configuration, selection objective, shock environment and clearance widgets are
the same as the Quick Selector — set them before extracting.

## Extracting

Click **"🔌 Extract from SolidWorks"**. On success the right panel shows:

- **Mass / Volume / Surface** metrics,
- **"Envelope (W x D x H)"** — the bounding box in mm,
- **"Center of Mass"** — X/Y/Z coordinates. If the CG sits above 60% of the equipment
  height you get a warning ("High CG ... overturn risk") — consider a lower mounting
  arrangement.
- a **"BOM (... components)"** expander listing the assembly's parts.

The isolator selection then runs automatically below ("Selection Result"), identical in
format to the Quick Selector results.

## When extraction fails

Common causes shown in the error message:

- SolidWorks is not running, or no document is active (for the active-document option).
- The file path doesn't exist (for the path option).

The "Subprocess stderr" / "Subprocess stdout" expanders hold the raw output for debugging.
If SolidWorks isn't available at all, use the **Quick Selector** tab and type the weights
from the spec sheet instead.
