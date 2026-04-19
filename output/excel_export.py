"""Export analysis results to Excel with multiple sheets."""
from __future__ import annotations
import pandas as pd
from pathlib import Path
import io


def export_to_excel(
    results: dict[str, pd.DataFrame],
    filepath: str | Path | None = None,
) -> bytes | None:
    """
    Export multiple DataFrames to an Excel file (one sheet per result).
    If filepath is None, returns bytes (for Streamlit download button).
    """
    buffer = io.BytesIO() if filepath is None else None
    target = buffer if buffer is not None else filepath

    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        for sheet_name, df in results.items():
            if df is None or df.empty:
                continue
            safe_name = sheet_name[:31]  # Excel sheet name limit
            df.to_excel(writer, sheet_name=safe_name, index=False)

            # Auto-fit column widths
            worksheet = writer.sheets[safe_name]
            for col in worksheet.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value is not None),
                    default=10,
                )
                worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

    if buffer is not None:
        return buffer.getvalue()
    return None
