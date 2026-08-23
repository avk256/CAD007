from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agentcad.llm.prompt_loader import load_prompt
from agentcad.models.unified_specification import UnifiedModelSpecification


class CodeGenerationResult(BaseModel):
    summary: str
    script_code: str = Field(description="Complete Python source without Markdown fences.")


class CodeGenerator:
    """LLM implementation layer: UnifiedModelSpecification -> FreeCAD Python."""

    def __init__(self, model):
        # IMPORTANT:
        # The system prompt is loaded as a literal SystemMessage, not as a
        # LangChain f-string template. This allows JSON/Python examples with
        # ordinary { ... } braces inside external prompt files.
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=load_prompt("code_generator.txt")),
                (
                    "human",
                    """UNIFIED MODEL SPECIFICATION:
{specification}

OUTPUT DIRECTORY:
{output_dir}

ATTEMPT:
{attempt}

PREVIOUS SCRIPT:
{previous_code}

EXECUTION / INSPECTION DIAGNOSTICS:
{diagnostics}
""",
                ),
            ]
        )
        self._chain = prompt | model.with_structured_output(CodeGenerationResult)

    @staticmethod
    def _clean_code(text: str) -> str:
        code = text.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code

    def generate(
        self,
        specification: UnifiedModelSpecification,
        output_dir: str,
        attempt: int,
        previous_code: str = "",
        diagnostics: str = "",
    ) -> CodeGenerationResult:
        result = self._chain.invoke(
            {
                "specification": specification.model_dump_json(indent=2),
                "output_dir": output_dir,
                "attempt": attempt,
                "previous_code": previous_code,
                "diagnostics": diagnostics,
            }
        )
        result.script_code = self._clean_code(result.script_code)
        return result
