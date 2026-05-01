# pipeline/llm.py
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from config import cfg

# Reduce CUDA memory fragmentation — harmless if already set
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def _auto_quantise() -> bool:
    """Return True if free VRAM is too low for safe bf16 inference."""
    if not torch.cuda.is_available():
        return True  # CPU path — always quantise
    free_bytes = torch.cuda.mem_get_info()[0]
    free_gib = free_bytes / (1024 ** 3)
    if free_gib < cfg.llm.min_free_vram_gib:
        print(f"  ⚠️  Only {free_gib:.1f} GiB VRAM free — auto-enabling 4-bit quantisation")
        return True
    return False


def load_model(quantise: bool = False):
    """
    Load Gemma 4 E4B locally.

    quantise=False  → bf16, requires ~8 GB VRAM (recommended with GPU)
    quantise=True   → 4-bit via bitsandbytes, requires ~5 GB VRAM / runs on CPU

    If quantise=False but free VRAM is below the threshold, 4-bit is
    enabled automatically to avoid OOM during inference.
    """
    model_id = cfg.llm.model_id
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    if not quantise:
        quantise = _auto_quantise()

    if quantise:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    model.eval()
    return tokenizer, model


def ask(
    prompt: str,
    tokenizer,
    model,
    temperature: float | None = None,
    max_new_tokens: int | None = None,
) -> str:
    """
    Send a single-turn prompt to Gemma 4 and return the response text.
    Uses the model's chat template automatically.
    """
    if temperature is None:
        temperature = cfg.llm.temperature
    if max_new_tokens is None:
        max_new_tokens = cfg.llm.max_new_tokens

    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        return_tensors="pt",
        add_generation_prompt=True,
    )
    # transformers ≥ 5.x returns a BatchEncoding; earlier versions return a plain tensor
    if hasattr(inputs, "input_ids"):
        input_ids = inputs["input_ids"].to(model.device)
    else:
        input_ids = inputs.to(model.device)

    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )

    # Decode only the newly generated tokens
    new_tokens = output_ids[0][input_ids.shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
