"""Gemini/OpenAI-gateway judge for MultiBanana."""

from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path

from PIL import Image

METRIC_KEYS = {
    "Instruction Alignment": "instruction_alignment",
    "Reference Consistency": "reference_consistency",
    "Background-Subject Match": "background_subject_match",
    "Physical Realism": "physical_realism",
    "Visual Quality": "visual_quality",
}

_CLIENT = None


def create_evaluation_prompts(instruction: str):
    prompt_a = """You are a strict data rater specializing in grading multi-reference drien image generation. 
You will be given reference images, task instruction, and the generation results. 
Reference Images:"""
    prompt_b = f"""Editing Instruction: {instruction}
Final Output:"""
    prompt_c = """
Your task is to evaluate the effectiveness of replacement editing from five independent perspectives, each on a 10-point scale.
Note that the average score should be considered 4 points.

1. Text-Instruction Alignment
2. Reference Consistency
3. Background-Subject Match
4. Physical Realism
5. Visual Quality

Each of the five scores must be evaluated independently.

First explain the reasoning, then present the final assessment. Start the reasoning with 'Reasoning: '.

Format:
Instruction Alignment: <A number from 1 to 10>.
Reference Consistency: <A number from 1 to 10>.
Background-Subject Match: <A number from 1 to 10>.
Physical Realism: <A number from 1 to 10>.
Visual Quality: <A number from 1 to 10>.
"""
    return prompt_a, prompt_b, prompt_c


def _pil_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    from openai import OpenAI

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base = (os.environ.get("GEMINI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "").rstrip("/") or None
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for MultiBanana eval")
    _CLIENT = OpenAI(api_key=api_key, base_url=base)
    return _CLIENT


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL") or os.environ.get("BENCHMARK_JUDGE_MODEL") or os.environ.get("MULTIBANANA_JUDGE_MODEL") or "gpt-5.4"


def evaluate_sample(generated_path: Path, ref_paths: list[Path], prompt_path: Path) -> str:
    instruction = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
    prompt_a, prompt_b, prompt_c = create_evaluation_prompts(instruction)
    content = [{"type": "text", "text": prompt_a}]
    for ref in ref_paths:
        content.append(
            {"type": "image_url", "image_url": {"url": _pil_to_data_url(Image.open(ref))}}
        )
    content.append({"type": "text", "text": prompt_b})
    content.append(
        {"type": "image_url", "image_url": {"url": _pil_to_data_url(Image.open(generated_path))}}
    )
    content.append({"type": "text", "text": prompt_c})
    resp = _client().chat.completions.create(
        model=_model_name(),
        messages=[{"role": "user", "content": content}],
        max_tokens=8192,
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


def extract_scores(content: str) -> dict | None:
    patterns = {
        "Instruction Alignment": r"Instruction Alignment:\s*(\d+)",
        "Reference Consistency": r"Reference Consistency:\s*(\d+)",
        "Background-Subject Match": r"Background-Subject Match:\s*(\d+)",
        "Physical Realism": r"Physical Realism:\s*(\d+)",
        "Visual Quality": r"Visual Quality:\s*(\d+)",
    }
    scores = {}
    for metric, pattern in patterns.items():
        m = re.search(pattern, content)
        if m:
            scores[metric] = int(m.group(1))
    if len(scores) != 5:
        return None
    out = {METRIC_KEYS[k]: float(v) for k, v in scores.items()}
    out["score"] = round(sum(out.values()) / 5, 2)
    return out
