# workflows/python_code_gen_workflow.py
import base64
import io
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from fastmcp import Client
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from src.stores.llm.templates.locales.en.en_prompts import advanced_analysis_plan_prompt

# Resolve mcp_server.py relative to this file, so it works from any working directory
SERVER_PATH = Path(__file__).parent / "mcp_server.py"

# Charts come back from the sandbox as: <<FIG:title>>base64...<<ENDFIG>>
FIG_PATTERN = re.compile(r"<<FIG:(.*?)>>(.*?)<<ENDFIG>>", re.DOTALL)

# Prepended to every sandboxed script. Generated code calls show_fig() instead of plt.show().
SANDBOX_HELPERS = '''
import base64, io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def show_fig(title="Figure"):
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close()
    print(f"<<FIG:{title}>>{base64.b64encode(buf.getvalue()).decode()}<<ENDFIG>>")
'''

REPORT_PROMPT = """Write a short analysis report for business stakeholders.

User question:
{question}

Analysis output:
{execution_output}

Charts included in the report: {figure_titles}

Use exactly these sections, each starting with a line like "# Executive Summary":
# Executive Summary
# Key Findings
# Recommendations
# Suggested Next Steps

Use plain text only (no markdown symbols except the "# " heading lines).
Use only facts from the analysis output. Do not invent numbers."""


class PythonCodeGenWorkflow:
    """Handles Python code generation and advanced analysis workflow."""

    def __init__(self, client, system_prompt, output_dir: str = "reports"):
        self.client = client
        self.system_prompt = system_prompt
        self.output_dir = Path(output_dir)

    def plan_advanced_analysis(self, state: dict) -> dict:
        """Generate Python code for advanced analysis and visualization."""
        prompt = advanced_analysis_plan_prompt.format(
            user_request=state["question"],
            schema_block=state["schema"],
            sql_query=state["sql_v2"],
            df=state["df_v2"],
        )
        response = self.client.generate(prompt=prompt, system_instruction=self.system_prompt)

        if not response.text:
            raise RuntimeError("Empty content returned by the LLM.")

        m = re.search(r"<execute_python>(.*?)</execute_python>", response.text, re.DOTALL | re.IGNORECASE)
        return {"analysis_plan_code": m.group(1).strip() if m else response.text.strip()}

    async def execution(self, state: dict) -> dict:
        """Run the generated code in the Docker sandbox; separate text output from charts."""
        script = self._prepare_script(state["analysis_plan_code"], state.get("df_v2"))
        raw = await self._call_mcp_tool(script)

        figures = [
            {"title": t.strip() or "Figure", "b64": b.strip()}
            for t, b in FIG_PATTERN.findall(raw)
        ]
        # Remove the base64 blobs so the LLM only ever sees the readable text
        text = FIG_PATTERN.sub("[chart omitted]", raw).strip()
        return {"execution_output": text, "figures": figures}

    def _prepare_script(self, code: str, df) -> str:
        """Prepend helpers and DataFrame reconstruction so the script has `df` and `show_fig`."""
        preamble = SANDBOX_HELPERS + "\nimport pandas as pd\n"
        if df is not None:
            preamble += f"df = pd.read_json(io.StringIO({df.to_json(orient='split')!r}), orient='split')\n"
        return preamble + "\n" + code

    async def _call_mcp_tool(self, code: str) -> str:
        """Start the MCP server over stdio, call run_python, return the text result."""
        async with Client(str(SERVER_PATH)) as mcp_client:
            result = await mcp_client.call_tool("run_python", {"code": code})
            content = getattr(result, "content", result)
            return "\n".join(c.text for c in content if hasattr(c, "text"))

    def reflect_and_check_analysis(self, state: dict) -> dict:
        """Reflect on analysis and check for errors."""
        reflect_analysis_prompt = """
        You are a senior data analyst reviewing an advanced analysis and visualization plan.

        User question:
        {question}

        Schema:
        {schema}

        SQL query:
        {sql_query}

        Generated Python code:
        {analysis_plan_code}

        execution results:
        {execution_output}


        Review the Python code execution results and check for errors and check if the analysis meets the user's request
        and evaluate it from (1-10) as quality score{analysis_plan_score} for the analysis
        """

        prompt = reflect_analysis_prompt.format(
            question=state["question"],
            schema=state["schema"],
            sql_query=state["sql_v2"],
            analysis_plan_code=state["analysis_plan_code"],
            execution_output=state["execution_output"],
            analysis_plan_score=state["analysis_plan_score"],
        )
        response = self.client.generate(prompt=prompt, system_instruction=self.system_prompt)
        return {"reflection": response.text}

    def output_pdf(self, state: dict) -> dict:
        """One LLM call writes the report text; then text and charts are combined into a PDF."""
        figures = state.get("figures", [])

        # 1) Ask the LLM for the narrative (summary, findings, recommendations, next steps)
        prompt = REPORT_PROMPT.format(
            question=state["question"],
            execution_output=state["execution_output"][:8000],
            figure_titles=[f["title"] for f in figures],
        )
        report_text = self.client.generate(prompt=prompt, system_instruction=self.system_prompt).text or ""

        # 2) Build the PDF: "# " lines become headings, other lines become paragraphs
        styles = getSampleStyleSheet()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = self.output_dir / f"analysis_report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm)

        story = [
            Paragraph("Analysis Report", styles["Title"]),
            Paragraph(escape(state["question"]), styles["Italic"]),
            Spacer(1, 12),
        ]
        for line in report_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                story.append(Paragraph(escape(line[2:]), styles["Heading2"]))
            else:
                # escape() keeps characters like < and & from breaking ReportLab's markup
                story.append(Paragraph(escape(line), styles["BodyText"]))

        # 3) Charts, scaled to fit the page width
        if figures:
            story.append(Paragraph("Charts", styles["Heading2"]))
            for fig in figures:
                png = io.BytesIO(base64.b64decode(fig["b64"]))
                story.append(Image(png, width=doc.width, height=11 * cm, kind="proportional"))
                story.append(Paragraph(escape(fig["title"]), styles["Italic"]))
                story.append(Spacer(1, 10))

        doc.build(story)
        return {"pdf_path": str(pdf_path)}